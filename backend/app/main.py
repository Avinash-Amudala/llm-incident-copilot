import logging
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .config import CORS_ORIGINS, MAX_CHUNKS
from .storage import save_upload
from .ingest import chunk_text, detect_metadata, smart_chunk_logs, extract_log_stats
from .llm import ollama_embed, ollama_chat, check_ollama_connection, get_available_models, get_inference_provider
from .retrieval import upsert_chunks, search as qdrant_search
from .models import (
    IngestResponse, AnalyzeRequest, AnalyzeResponse, EvidenceItem, DatasetInfo
)

# configure logging to see what's happening
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

MAX_FILE_SIZE_MB = 10  # warn for files larger than this

app = FastAPI(
    title="LLM Incident Copilot",
    description="Evidence-based incident debugging with LLMs and vector search",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# simple in-memory conversation storage (good enough for demo)
conversations: dict = {}


@app.get("/health")
def health():
    """Quick health check for the API."""
    ollama_ok = check_ollama_connection()
    models = get_available_models() if ollama_ok else []
    provider = get_inference_provider()
    return {
        "ok": True,
        "ollama_connected": ollama_ok,
        "inference_provider": provider,
        "available_models": models[:5],
        "max_chunks": MAX_CHUNKS,
    }


@app.post("/ingest", response_model=IngestResponse)
async def ingest(file: UploadFile = File(...)):
    """
    Upload and ingest a log file.

    Parses the file, chunks it smartly, generates embeddings,
    and stores everything in the vector DB for later search.
    """
    content = await file.read()
    file_size_mb = len(content) / (1024 * 1024)
    logger.info(f"Received file: {file.filename} ({file_size_mb:.2f} MB)")

    if file_size_mb > MAX_FILE_SIZE_MB:
        logger.warning(f"Large file detected ({file_size_mb:.2f} MB). Processing may take a while.")

    save_upload(file.filename, content)
    text = content.decode("utf-8", errors="replace")

    # get stats before chunking
    logger.info("Extracting log statistics...")
    stats = extract_log_stats(text)
    logger.info(f"Stats: {stats['total_lines']} lines, {stats['error_count']} errors, {stats['warn_count']} warnings")

    # use smart chunking for structured logs
    logger.info("Chunking log file...")
    smart_chunks = smart_chunk_logs(text)
    if smart_chunks:
        chunk_texts = [c["text"] for c in smart_chunks]
        metas = []
        for i, c in enumerate(smart_chunks):
            meta = detect_metadata(c["text"], file.filename)
            meta.update(c.get("metadata", {}))
            metas.append(meta)
    else:
        # fallback to basic chunking
        chunk_texts = chunk_text(text)
        metas = [detect_metadata(c, file.filename) for c in chunk_texts]

    original_count = len(chunk_texts)
    logger.info(f"Created {original_count} chunks")

    # limit chunks to prevent timeout - prioritize chunks with errors/warnings
    if len(chunk_texts) > MAX_CHUNKS:
        logger.warning(f"Too many chunks ({len(chunk_texts)}), limiting to {MAX_CHUNKS}")

        # sort by error/warning count to keep the most interesting chunks
        indexed = list(enumerate(zip(chunk_texts, metas)))
        indexed.sort(key=lambda x: (
            x[1][1].get("error_count", 0) * 10 + x[1][1].get("warn_count", 0)
        ), reverse=True)

        # take top chunks by importance
        selected = indexed[:MAX_CHUNKS]
        selected.sort(key=lambda x: x[0])  # restore original order

        chunk_texts = [x[1][0] for x in selected]
        metas = [x[1][1] for x in selected]
        logger.info(f"Selected {len(chunk_texts)} most relevant chunks")

    # generate embeddings
    logger.info(f"Generating embeddings for {len(chunk_texts)} chunks...")
    vectors = ollama_embed(chunk_texts)

    # store in vector db
    logger.info("Storing in vector database...")
    created = upsert_chunks(vectors, chunk_texts, metas)
    logger.info(f"Successfully stored {created} chunks")

    # add note if we limited chunks
    if original_count > MAX_CHUNKS:
        stats["note"] = f"File had {original_count} chunks, limited to {MAX_CHUNKS} most relevant"

    return IngestResponse(filename=file.filename, chunks_created=created, stats=stats)


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest):
    """
    Ask a question about the ingested logs.

    Retrieves relevant chunks via vector search, sends them to the LLM
    with your question, and returns a structured analysis.
    """
    logger.info(f"Analyzing question: {req.question[:100]}...")

    # retrieve relevant chunks from vector db
    logger.info("Embedding question...")
    qv = ollama_embed([req.question])[0]

    logger.info(f"Searching for top {req.top_k} relevant chunks...")
    hits = qdrant_search(qv, top_k=req.top_k)

    if not hits:
        logger.warning("No chunks found in vector DB. Has a log file been ingested?")
        return AnalyzeResponse(
            summary="No log data found. Please upload a log file first using the Upload panel.",
            probable_root_cause="N/A - no data ingested",
            confidence="low",
            evidence=[],
            next_steps=["Upload a log file using the Upload Logs panel", "Try one of the sample logs from data/sample_logs/"],
            conversation_id=None,
        )

    logger.info(f"Found {len(hits)} relevant chunks")

    # build evidence context for the LLM
    evidence_blocks = []
    evidence_items = []
    for h in hits:
        payload = h.payload or {}
        text = payload.get("text", "")
        filename = payload.get("filename", "unknown")
        chunk_id = payload.get("chunk_id", str(h.id))
        timestamp = payload.get("timestamp")
        level = payload.get("level")
        quote = (text[:350] + "...") if len(text) > 350 else text

        evidence_items.append(EvidenceItem(
            chunk_id=chunk_id,
            filename=filename,
            quote=quote,
            timestamp=timestamp,
            level=level
        ))
        evidence_blocks.append(f"[{chunk_id} | {filename} | {timestamp or 'no-ts'}]\n{text}")

    # handle conversation context if provided
    conversation_context = ""
    conv_id = req.conversation_id
    if conv_id and conv_id in conversations:
        prev_exchanges = conversations[conv_id]
        conversation_context = "\n".join([
            f"Previous Q: {ex['q']}\nPrevious A: {ex['a'][:500]}..."
            for ex in prev_exchanges[-3:]  # last 3 exchanges
        ]) + "\n\n"

    system = (
        "You are an expert SRE/DevOps engineer analyzing production logs to debug incidents. "
        "Your job is to find the root cause and provide actionable next steps.\n\n"
        "RULES:\n"
        "1. Only make claims supported by the log evidence provided\n"
        "2. Cite specific chunk_ids when referencing evidence\n"
        "3. If evidence is insufficient, say so honestly\n"
        "4. Focus on actionable debugging steps\n"
        "5. Look for error patterns, stack traces, and timing correlations\n"
        "6. Be concise but thorough"
    )

    user = (
        f"{conversation_context}"
        f"QUESTION: {req.question}\n\n"
        f"LOG EVIDENCE ({len(evidence_blocks)} chunks):\n\n"
        + "\n\n---\n\n".join(evidence_blocks) + "\n\n"
        "Provide your analysis in this format:\n"
        "## Summary\n(2-4 sentences on what you found)\n\n"
        "## Root Cause\n(Your hypothesis based on evidence)\n\n"
        "## Confidence\nlow|medium|high\n\n"
        "## Evidence\n(Which chunk_ids support your analysis)\n\n"
        "## Next Steps\n(3-5 concrete debugging actions)\n"
    )

    logger.info("Sending to LLM for analysis...")
    raw = ollama_chat(system, user)
    logger.info(f"Got LLM response ({len(raw)} chars)")

    # parse the LLM response - look for structured sections
    summary = raw.strip()
    probable = ""
    confidence = "medium"
    next_steps = []

    # try to extract sections from markdown-formatted response
    lines = raw.split('\n')
    current_section = None
    section_content = []

    for line in lines:
        line_lower = line.lower().strip()
        if line_lower.startswith('## summary') or line_lower.startswith('**summary'):
            current_section = 'summary'
            section_content = []
        elif line_lower.startswith('## root cause') or line_lower.startswith('**root cause'):
            if current_section == 'summary':
                summary = '\n'.join(section_content).strip()
            current_section = 'root_cause'
            section_content = []
        elif line_lower.startswith('## confidence') or line_lower.startswith('**confidence'):
            if current_section == 'root_cause':
                probable = '\n'.join(section_content).strip()
            current_section = 'confidence'
            section_content = []
        elif line_lower.startswith('## evidence') or line_lower.startswith('**evidence'):
            if current_section == 'confidence':
                conf_text = '\n'.join(section_content).lower()
                if 'high' in conf_text:
                    confidence = 'high'
                elif 'low' in conf_text:
                    confidence = 'low'
            current_section = 'evidence'
            section_content = []
        elif line_lower.startswith('## next steps') or line_lower.startswith('**next steps'):
            current_section = 'next_steps'
            section_content = []
        elif current_section:
            section_content.append(line)

    # capture last section
    if current_section == 'next_steps' and section_content:
        for line in section_content:
            line = line.strip()
            if line and (line.startswith('-') or line.startswith('*') or line[0].isdigit()):
                step = line.lstrip('-*0123456789. ')
                if step:
                    next_steps.append(step)

    # fallback if parsing didn't work
    if not probable:
        probable = "See summary above for detailed analysis."
    if not next_steps:
        next_steps = [
            "Review the cited log chunks around their timestamps",
            "Check for related errors in adjacent time windows",
            "Look for config or deployment changes before the incident",
            "Increase log verbosity and reproduce if possible"
        ]

    # store in conversation history
    if not conv_id:
        conv_id = f"conv_{len(conversations)}"
    if conv_id not in conversations:
        conversations[conv_id] = []
    conversations[conv_id].append({"q": req.question, "a": summary})

    return AnalyzeResponse(
        summary=summary,
        probable_root_cause=probable,
        confidence=confidence,
        evidence=evidence_items,
        next_steps=next_steps[:7],  # cap at 7 steps
        conversation_id=conv_id,
    )


@app.get("/datasets", response_model=list[DatasetInfo])
def list_datasets():
    """
    List available sample datasets that can be loaded.
    Scans the data directory for log files.
    """
    datasets = []
    data_dir = Path(__file__).parent.parent.parent / "data"

    # sample logs
    sample_dir = data_dir / "sample_logs"
    if sample_dir.exists():
        for f in sample_dir.glob("*.log"):
            content = f.read_text(errors="replace")
            lines = len(content.splitlines())
            datasets.append(DatasetInfo(
                name=f.stem,
                path=str(f.relative_to(data_dir.parent)),
                description=f"Sample incident log: {f.stem.replace('_', ' ')}",
                line_count=lines,
                format="structured"
            ))

    # loghub datasets
    loghub_dir = data_dir / "logs" / "loghub"
    if loghub_dir.exists():
        for subdir in loghub_dir.iterdir():
            if subdir.is_dir():
                log_files = list(subdir.glob("*.log"))
                if log_files:
                    total_lines = sum(
                        len(f.read_text(errors="replace").splitlines())
                        for f in log_files[:3]  # sample first 3
                    )
                    datasets.append(DatasetInfo(
                        name=subdir.name,
                        path=str(subdir.relative_to(data_dir.parent)),
                        description=f"LogHub {subdir.name} dataset",
                        line_count=total_lines,
                        format="java_structured"
                    ))

    return datasets


@app.get("/stats")
def get_stats():
    """
    Get overall stats about ingested data.
    """
    # this would query Qdrant for collection stats in a real impl
    return {
        "total_chunks": "Query Qdrant for actual count",
        "conversations": len(conversations),
        "status": "healthy"
    }
