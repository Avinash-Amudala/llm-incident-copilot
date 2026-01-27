from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class IngestResponse(BaseModel):
    filename: str
    chunks_created: int
    stats: Optional[Dict[str, Any]] = None


class SearchHit(BaseModel):
    chunk_id: str
    score: float
    filename: str
    text: str


class AnalyzeRequest(BaseModel):
    question: str = Field(..., min_length=1)
    top_k: int = 6
    conversation_id: Optional[str] = None


class EvidenceItem(BaseModel):
    chunk_id: str
    filename: str
    quote: str
    timestamp: Optional[str] = None
    level: Optional[str] = None


class AnalyzeResponse(BaseModel):
    summary: str
    probable_root_cause: str
    confidence: str  # low | medium | high
    evidence: List[EvidenceItem]
    next_steps: List[str]
    conversation_id: Optional[str] = None


class LogStats(BaseModel):
    """Stats about an ingested log file."""
    total_lines: int
    format: str
    error_count: int
    warn_count: int
    info_count: int
    debug_count: int
    first_timestamp: Optional[str]
    last_timestamp: Optional[str]
    loggers: List[str]


class TimelineEvent(BaseModel):
    """A single event in a timeline view."""
    timestamp: str
    level: str
    message: str
    source: Optional[str] = None


class TimelineResponse(BaseModel):
    """Response for timeline endpoint."""
    events: List[TimelineEvent]
    total_count: int
    error_count: int
    warn_count: int


class DatasetInfo(BaseModel):
    """Info about an available sample dataset."""
    name: str
    path: str
    description: str
    line_count: int
    format: str

