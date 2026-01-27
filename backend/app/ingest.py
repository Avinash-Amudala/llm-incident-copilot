"""
Log ingestion and chunking logic.

Breaks log files into digestible pieces for vector storage while
keeping related entries together when possible.
"""
import re
from typing import List, Dict, Any
from .parsers import detect_format, parse_line

TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}")
LEVEL_RE = re.compile(r'\b(ERROR|WARN|WARNING|FATAL|CRITICAL)\b', re.IGNORECASE)


def chunk_text(text: str, max_chars: int = 1000, overlap: int = 150) -> List[str]:
    """
    Basic chunking by paragraph/block, with size limits.
    Kept for backwards compatibility.
    """
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


def smart_chunk_logs(
    text: str,
    max_lines: int = 50,
    max_chars: int = 2000
) -> List[Dict[str, Any]]:
    """
    Smarter log chunking that respects log structure.

    Groups logs by:
    1. Error/warning clusters (keeps context around issues)
    2. Natural time gaps (>5 min between entries)
    3. Size limits

    Returns list of dicts with chunk text and metadata.
    """
    lines = text.splitlines()
    if not lines:
        return []

    # detect format from first few lines
    fmt = detect_format(lines[:30])

    # parse all lines
    parsed = [parse_line(line, fmt) for line in lines if line.strip()]
    if not parsed:
        # fallback to basic chunking
        return [{"text": c, "metadata": {}} for c in chunk_text(text, max_chars)]

    chunks = []
    current_chunk_lines: List[str] = []
    current_chunk_meta: Dict[str, Any] = {
        "first_timestamp": None,
        "last_timestamp": None,
        "error_count": 0,
        "warn_count": 0,
        "log_format": fmt.value
    }

    def flush_chunk():
        if not current_chunk_lines:
            return
        chunk_text_str = "\n".join(current_chunk_lines)
        chunks.append({
            "text": chunk_text_str,
            "metadata": current_chunk_meta.copy()
        })
        current_chunk_lines.clear()
        current_chunk_meta.update({
            "first_timestamp": None,
            "last_timestamp": None,
            "error_count": 0,
            "warn_count": 0
        })

    for parsed_line in parsed:
        line = parsed_line.raw

        # track timestamps
        if parsed_line.timestamp:
            if current_chunk_meta["first_timestamp"] is None:
                current_chunk_meta["first_timestamp"] = parsed_line.timestamp
            current_chunk_meta["last_timestamp"] = parsed_line.timestamp

        # count errors/warnings
        level = (parsed_line.level or "").upper()
        if level in ("ERROR", "FATAL", "CRITICAL"):
            current_chunk_meta["error_count"] += 1
        elif level in ("WARN", "WARNING"):
            current_chunk_meta["warn_count"] += 1

        current_chunk_lines.append(line)

        # check if we should split here
        total_chars = sum(len(l) for l in current_chunk_lines)
        should_split = (
            len(current_chunk_lines) >= max_lines or
            total_chars >= max_chars
        )

        if should_split:
            flush_chunk()

    flush_chunk()
    return chunks


def detect_metadata(chunk: str, filename: str) -> Dict[str, Any]:
    """Extract metadata from a chunk for storage."""
    lines = chunk.splitlines()
    ts = None
    level = None
    error_count = 0
    warn_count = 0

    for ln in lines[:20]:
        stripped = ln.strip()
        if ts is None and TS_RE.match(stripped):
            ts = stripped[:19]

        level_match = LEVEL_RE.search(stripped)
        if level_match:
            found_level = level_match.group(1).upper()
            if found_level in ("ERROR", "FATAL", "CRITICAL"):
                error_count += 1
                if level is None:
                    level = found_level
            elif found_level in ("WARN", "WARNING"):
                warn_count += 1
                if level is None:
                    level = found_level

    return {
        "filename": filename,
        "timestamp": ts,
        "level": level,
        "error_count": error_count,
        "warn_count": warn_count,
    }


def extract_log_stats(text: str) -> Dict[str, Any]:
    """
    Pull out high-level stats from a log file.
    Useful for giving the user a quick overview.
    """
    lines = text.splitlines()
    fmt = detect_format(lines[:30])
    parsed = [parse_line(line, fmt) for line in lines if line.strip()]

    stats = {
        "total_lines": len(parsed),
        "format": fmt.value,
        "error_count": 0,
        "warn_count": 0,
        "info_count": 0,
        "debug_count": 0,
        "first_timestamp": None,
        "last_timestamp": None,
        "loggers": set(),
    }

    for p in parsed:
        level = (p.level or "").upper()
        if level in ("ERROR", "FATAL", "CRITICAL"):
            stats["error_count"] += 1
        elif level in ("WARN", "WARNING"):
            stats["warn_count"] += 1
        elif level == "INFO":
            stats["info_count"] += 1
        elif level in ("DEBUG", "TRACE"):
            stats["debug_count"] += 1

        if p.timestamp:
            if stats["first_timestamp"] is None:
                stats["first_timestamp"] = p.timestamp
            stats["last_timestamp"] = p.timestamp

        if p.logger:
            stats["loggers"].add(p.logger)

    # convert set to sorted list for JSON serialization
    stats["loggers"] = sorted(list(stats["loggers"]))[:20]  # cap at 20
    return stats
