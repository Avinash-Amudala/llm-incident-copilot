import re
from typing import List, Dict

TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}")


def chunk_text(text: str, max_chars: int = 1000, overlap: int = 150) -> List[str]:
    """Chunk text by splitting on blank lines, then by size with overlap."""
    blocks = re.split(r"\n\s*\n", text.strip())
    chunks: List[str] = []

    def push_with_overlap(s: str):
        s = s.strip()
        if not s:
            return
        if len(s) <= max_chars:
            chunks.append(s)
            return
        start = 0
        while start < len(s):
            end = min(start + max_chars, len(s))
            chunks.append(s[start:end])
            if end == len(s):
                break
            start = max(0, end - overlap)

    for b in blocks:
        push_with_overlap(b)

    return chunks


def detect_metadata(chunk: str, filename: str) -> Dict:
    """Extract minimal metadata from a chunk."""
    lines = chunk.splitlines()
    ts = None
    for ln in lines[:10]:
        if TS_RE.match(ln.strip()):
            ts = ln.strip()[:19]
            break
    return {"filename": filename, "timestamp": ts}

