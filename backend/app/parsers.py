"""
Log format auto-detection and parsing.

Supports common log formats you'd see in production:
- JSON (one object per line)
- Logfmt (key=value pairs)
- Syslog (RFC 3164 style)
- Hadoop/Java structured logs
- Zookeeper logs
- Kubernetes events (JSON)
"""
import re
import json
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum


class LogFormat(Enum):
    JSON = "json"
    LOGFMT = "logfmt"
    SYSLOG = "syslog"
    JAVA_STRUCTURED = "java_structured"
    PLAIN = "plain"


@dataclass
class ParsedLogLine:
    """A single parsed log entry with extracted fields."""
    raw: str
    timestamp: Optional[str] = None
    level: Optional[str] = None
    message: Optional[str] = None
    logger: Optional[str] = None
    thread: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None


# Patterns for format detection and parsing
JAVA_LOG_PATTERN = re.compile(
    r'^(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}[,\.:]\d{3})\s+'
    r'(INFO|WARN|ERROR|DEBUG|TRACE|FATAL)\s+'
    r'\[([^\]]+)\]\s+'
    r'([a-zA-Z][\w\.]+(?::\w+)?)'
    r'[:\s-]*(.*)$'
)

ZK_LOG_PATTERN = re.compile(
    r'^(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}[,\.:]\d{3})\s*-\s*'
    r'(INFO|WARN|ERROR|DEBUG|TRACE|FATAL)\s+'
    r'\[([^\]]+)\]\s*-\s*(.*)$'
)

SYSLOG_PATTERN = re.compile(
    r'^(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+'
    r'(\S+)\s+'
    r'([^\[:\s]+)(?:\[(\d+)\])?:\s*(.*)$'
)

LOGFMT_PATTERN = re.compile(r'(\w+)=(?:"([^"]*)"|([^\s]*))')
TIMESTAMP_PATTERN = re.compile(r'\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}')
LEVEL_PATTERN = re.compile(r'\b(INFO|WARN|WARNING|ERROR|DEBUG|TRACE|FATAL|CRITICAL)\b', re.IGNORECASE)


def detect_format(sample_lines: List[str]) -> LogFormat:
    """Figure out what kind of log file we're dealing with."""
    if not sample_lines:
        return LogFormat.PLAIN
    
    json_count = 0
    logfmt_count = 0
    java_count = 0
    zk_count = 0
    syslog_count = 0
    
    for line in sample_lines[:20]:
        line = line.strip()
        if not line:
            continue
        
        # check for JSON (starts with { and valid json)
        if line.startswith('{'):
            try:
                json.loads(line)
                json_count += 1
                continue
            except:
                pass
        
        # check for logfmt (multiple key=value patterns)
        if len(LOGFMT_PATTERN.findall(line)) >= 3:
            logfmt_count += 1
            continue
        
        # check Zookeeper format (has the dash separator)
        if ZK_LOG_PATTERN.match(line):
            zk_count += 1
            continue
        
        # check Java/Hadoop format
        if JAVA_LOG_PATTERN.match(line):
            java_count += 1
            continue
        
        # check syslog
        if SYSLOG_PATTERN.match(line):
            syslog_count += 1
    
    # pick the format with most matches
    counts = [
        (json_count, LogFormat.JSON),
        (logfmt_count, LogFormat.LOGFMT),
        (java_count + zk_count, LogFormat.JAVA_STRUCTURED),
        (syslog_count, LogFormat.SYSLOG),
    ]
    best = max(counts, key=lambda x: x[0])
    return best[1] if best[0] > 0 else LogFormat.PLAIN


def parse_line(line: str, fmt: LogFormat) -> ParsedLogLine:
    """Parse a single log line based on detected format."""
    line = line.strip()
    result = ParsedLogLine(raw=line)
    
    if fmt == LogFormat.JSON:
        return _parse_json_line(line)
    elif fmt == LogFormat.LOGFMT:
        return _parse_logfmt_line(line)
    elif fmt == LogFormat.JAVA_STRUCTURED:
        return _parse_java_line(line)
    elif fmt == LogFormat.SYSLOG:
        return _parse_syslog_line(line)
    else:
        return _parse_plain_line(line)


def _parse_json_line(line: str) -> ParsedLogLine:
    """Handle JSON log entries like you'd get from structured logging libs."""
    result = ParsedLogLine(raw=line)
    try:
        data = json.loads(line)
        # common field names across different logging frameworks
        result.timestamp = data.get('timestamp') or data.get('time') or data.get('@timestamp') or data.get('ts')
        result.level = data.get('level') or data.get('severity') or data.get('log_level')
        result.message = data.get('message') or data.get('msg') or data.get('log')
        result.logger = data.get('logger') or data.get('name') or data.get('source')
        result.thread = data.get('thread') or data.get('thread_name')
        result.extra = {k: v for k, v in data.items()
                       if k not in ['timestamp', 'time', '@timestamp', 'ts', 'level',
                                   'severity', 'log_level', 'message', 'msg', 'log',
                                   'logger', 'name', 'source', 'thread', 'thread_name']}
    except:
        result.message = line
    return result


def _parse_logfmt_line(line: str) -> ParsedLogLine:
    """Parse key=value style logs (common in Go apps, Prometheus, etc)."""
    result = ParsedLogLine(raw=line)
    fields = {}
    for match in LOGFMT_PATTERN.finditer(line):
        key = match.group(1)
        value = match.group(2) if match.group(2) is not None else match.group(3)
        fields[key.lower()] = value

    result.timestamp = fields.get('time') or fields.get('timestamp') or fields.get('ts')
    result.level = fields.get('level') or fields.get('lvl') or fields.get('severity')
    result.message = fields.get('msg') or fields.get('message')
    result.logger = fields.get('logger') or fields.get('component') or fields.get('caller')
    result.extra = {k: v for k, v in fields.items()
                   if k not in ['time', 'timestamp', 'ts', 'level', 'lvl', 'severity',
                               'msg', 'message', 'logger', 'component', 'caller']}
    return result


def _parse_java_line(line: str) -> ParsedLogLine:
    """Handle Hadoop/Zookeeper style Java logs."""
    result = ParsedLogLine(raw=line)

    # try zookeeper pattern first (has the dash separator)
    zk_match = ZK_LOG_PATTERN.match(line)
    if zk_match:
        result.timestamp = zk_match.group(1)
        result.level = zk_match.group(2)
        # thread contains class info like "main:QuorumPeerConfig@101"
        thread_info = zk_match.group(3)
        if ':' in thread_info:
            parts = thread_info.split(':', 1)
            result.thread = parts[0]
            result.logger = parts[1] if len(parts) > 1 else None
        else:
            result.thread = thread_info
        result.message = zk_match.group(4)
        return result

    # try standard java log pattern
    java_match = JAVA_LOG_PATTERN.match(line)
    if java_match:
        result.timestamp = java_match.group(1)
        result.level = java_match.group(2)
        result.thread = java_match.group(3)
        result.logger = java_match.group(4)
        result.message = java_match.group(5)
        return result

    # fallback: try to extract what we can
    return _parse_plain_line(line)


def _parse_syslog_line(line: str) -> ParsedLogLine:
    """Parse traditional syslog format (RFC 3164)."""
    result = ParsedLogLine(raw=line)
    match = SYSLOG_PATTERN.match(line)
    if match:
        result.timestamp = match.group(1)
        result.extra = {"host": match.group(2)}
        result.logger = match.group(3)
        if match.group(4):
            result.extra["pid"] = match.group(4)
        result.message = match.group(5)
    else:
        result.message = line
    return result


def _parse_plain_line(line: str) -> ParsedLogLine:
    """Best effort parsing for unknown formats."""
    result = ParsedLogLine(raw=line)

    # try to find a timestamp
    ts_match = TIMESTAMP_PATTERN.search(line)
    if ts_match:
        result.timestamp = ts_match.group(0)

    # try to find a log level
    level_match = LEVEL_PATTERN.search(line)
    if level_match:
        result.level = level_match.group(1).upper()

    result.message = line
    return result


def parse_log_file(content: str) -> Tuple[LogFormat, List[ParsedLogLine]]:
    """Parse an entire log file, auto-detecting format."""
    lines = content.splitlines()
    fmt = detect_format(lines)
    parsed = [parse_line(line, fmt) for line in lines if line.strip()]
    return fmt, parsed


def extract_trace_ids(parsed_lines: List[ParsedLogLine]) -> Dict[str, List[int]]:
    """
    Find request/trace IDs to group related logs together.
    Returns a dict mapping trace_id -> list of line indices.
    """
    trace_patterns = [
        re.compile(r'(?:request[_-]?id|req[_-]?id|trace[_-]?id|correlation[_-]?id|x-request-id)[=:\s]+([a-zA-Z0-9_-]+)', re.IGNORECASE),
        re.compile(r'(?:transaction|txn|tx)[_-]?(?:id)?[=:\s]+([a-zA-Z0-9_-]+)', re.IGNORECASE),
    ]

    trace_map: Dict[str, List[int]] = {}
    for idx, line in enumerate(parsed_lines):
        text = line.raw
        for pattern in trace_patterns:
            match = pattern.search(text)
            if match:
                trace_id = match.group(1)
                if trace_id not in trace_map:
                    trace_map[trace_id] = []
                trace_map[trace_id].append(idx)
                break

    return trace_map

