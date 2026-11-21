"""Structured JSON logs with secret redaction. Request bodies are never logged (Principle II)."""

import json
import logging
import re
import sys
from datetime import UTC, datetime

_SENSITIVE = r"(password|passwd|token|authorization|cookie|refresh|secret|otp)"
# Bearer tokens first, then key=value, key: value, "key": "value".
_PATTERNS = [
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+"),
    re.compile(rf"(?i)(\"?{_SENSITIVE}[\w-]*\"?\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|[^\s,;}}]+)"),
]
REDACTED = "[REDACTED]"


def redact(text: str) -> str:
    for pattern in _PATTERNS:
        text = pattern.sub(lambda m: m.group(1) + REDACTED, text)
    return text


class RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = None
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            # Exception type only; tracebacks can carry local values.
            entry["exc"] = record.exc_info[0].__name__ if record.exc_info[0] else None
        return json.dumps(entry, ensure_ascii=False)


def setup_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactFilter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers[:] = []
        lg.propagate = True
