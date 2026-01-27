from pathlib import Path
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from .config import CORS_ORIGINS
from .storage import save_upload
from .ingest import chunk_text, detect_metadata, smart_chunk_logs, extract_log_stats
from .llm import ollama_embed, ollama_chat
from .retrieval import upsert_chunks, search as qdrant_search
from .models import (
    IngestResponse, AnalyzeRequest, AnalyzeResponse, EvidenceItem, DatasetInfo
)

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
    return {"ok": True}


@app.post("/ingest", response_model=IngestResponse)
async def ingest(file: UploadFile = File(...)):
    """
    Upload and ingest a log file.

    Parses the file, chunks it smartly, generates embeddings,
    and stores everything in the vector DB for later search.
    """
    content = await file.read()
    save_upload(file.filename, content)
    text = content.decode("utf-8", errors="replace")

    # get stats before chunking
    stats = extract_log_stats(text)

    # use smart chunking for structured logs
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

    vectors = ollama_embed(chunk_texts)
    created = upsert_chunks(vectors, chunk_texts, metas)

    return IngestResponse(filename=file.filename, chunks_created=created, stats=stats)


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest):
    """
    Ask a question about the ingested logs.

    Retrieves relevant chunks via vector search, sends them to the LLM
    with your question, and returns a structured analysis.
    """
    # retrieve relevant chunks from vector db
    qv = ollama_embed([req.question])[0]
    hits = qdrant_search(qv, top_k=req.top_k)

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
        "You are an incident debugging assistant analyzing production logs. "
        "IMPORTANT RULES:\n"
        "1. Only make claims directly supported by the provided evidence\n"
        "2. Always cite chunk_ids when referencing evidence\n"
        "3. If evidence is insufficient, explicitly say so\n"
        "4. Focus on actionable insights, not speculation\n"
        "5. Consider temporal patterns in timestamps"
    )

    user = (
        f"{conversation_context}"
        f"Question:\n{req.question}\n\n"
        f"Evidence from logs:\n" + "\n\n---\n\n".join(evidence_blocks) + "\n\n"
        "Please provide:\n"
        "1) Summary (2-4 sentences describing what you found)\n"
        "2) Probable root cause (your best hypothesis based on evidence)\n"
        "3) Confidence: low|medium|high (be honest)\n"
        "4) Evidence citations: which chunk_ids support your analysis\n"
        "5) Next steps: 3-7 concrete debugging actions\n"
    )

    raw = ollama_chat(system, user)

    # parse the LLM response - look for structured sections
    summary = raw.strip()
    probable = "See summary above for details."
    confidence = "medium"
    next_steps = [
        "Review the cited log chunks around their timestamps",
        "Check for related errors in adjacent time windows",
        "Look for config or deployment changes before the incident",
        "Increase log verbosity and reproduce if possible"
    ]

    # try to extract confidence from the response
    lower = raw.lower()
    if "confidence:" in lower or "confidence :" in lower:
        if "low" in lower[lower.find("confidence"):lower.find("confidence")+30]:
            confidence = "low"
        elif "high" in lower[lower.find("confidence"):lower.find("confidence")+30]:
            confidence = "high"

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
        next_steps=next_steps,
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
