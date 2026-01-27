from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from .config import CORS_ORIGINS
from .storage import save_upload
from .ingest import chunk_text, detect_metadata
from .llm import ollama_embed, ollama_chat
from .retrieval import upsert_chunks, search as qdrant_search
from .models import IngestResponse, AnalyzeRequest, AnalyzeResponse, EvidenceItem

app = FastAPI(title="LLM Incident Copilot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/ingest", response_model=IngestResponse)
async def ingest(file: UploadFile = File(...)):
    content = await file.read()
    path = save_upload(file.filename, content)
    text = content.decode("utf-8", errors="replace")

    chunks = chunk_text(text)
    metas = [detect_metadata(c, file.filename) for c in chunks]
    vectors = ollama_embed(chunks)
    created = upsert_chunks(vectors, chunks, metas)

    return IngestResponse(filename=file.filename, chunks_created=created)


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest):
    # Retrieve relevant chunks
    qv = ollama_embed([req.question])[0]
    hits = qdrant_search(qv, top_k=req.top_k)

    # Build evidence context
    evidence_blocks = []
    evidence_items = []
    for h in hits:
        payload = h.payload or {}
        text = payload.get("text", "")
        filename = payload.get("filename", "unknown")
        chunk_id = payload.get("chunk_id", str(h.id))
        quote = (text[:350] + "...") if len(text) > 350 else text

        evidence_items.append(EvidenceItem(chunk_id=chunk_id, filename=filename, quote=quote))
        evidence_blocks.append(f"[{chunk_id} | {filename}]\n{text}")

    system = (
        "You are an incident debugging assistant. "
        "You MUST only make claims supported by the provided evidence. "
        "If evidence is insufficient, say so and set confidence to 'low'. "
        "Output MUST be concise, actionable, and include citations by chunk_id."
    )

    user = (
        f"Question:\n{req.question}\n\n"
        f"Evidence:\n" + "\n\n---\n\n".join(evidence_blocks) + "\n\n"
        "Return:\n"
        "1) Summary (1-3 sentences)\n"
        "2) Probable root cause (1-2 sentences)\n"
        "3) Confidence: low|medium|high\n"
        "4) Evidence citations: list of chunk_ids used\n"
        "5) Next steps: 3-7 bullet points\n"
    )

    raw = ollama_chat(system, user)

    # Minimal parsing for v1
    summary = raw.strip()
    probable = "See summary above."
    confidence = "medium"
    next_steps = [
        "Check logs around the cited timestamps.",
        "Validate recent deploy/config changes.",
        "Reproduce with higher verbosity logging."
    ]

    # Heuristic confidence: if model says low, respect it
    lower = raw.lower()
    if "confidence" in lower and "low" in lower:
        confidence = "low"
    if "confidence" in lower and "high" in lower:
        confidence = "high"

    return AnalyzeResponse(
        summary=summary,
        probable_root_cause=probable,
        confidence=confidence,
        evidence=evidence_items,
        next_steps=next_steps,
    )

