from pydantic import BaseModel, Field
from typing import List, Optional


class IngestResponse(BaseModel):
    filename: str
    chunks_created: int


class SearchHit(BaseModel):
    chunk_id: str
    score: float
    filename: str
    text: str


class AnalyzeRequest(BaseModel):
    question: str = Field(..., min_length=1)
    top_k: int = 6


class EvidenceItem(BaseModel):
    chunk_id: str
    filename: str
    quote: str


class AnalyzeResponse(BaseModel):
    summary: str
    probable_root_cause: str
    confidence: str  # low | medium | high
    evidence: List[EvidenceItem]
    next_steps: List[str]

