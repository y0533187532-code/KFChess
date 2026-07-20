"""JSON Lines logging with recursive masking of private values."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Mapping


REDACTED = "[REDACTED]"
_SENSITIVE_FRAGMENTS = (
    "password",
    "token",
    "secret",
    "authorization",
    "email",
    "phone",
    "hash",
)
_STANDARD_RECORD_KEYS = frozenset(logging.makeLogRecord({}).__dict__)


def _is_sensitive(key: str) -> bool:
    normalized = key.casefold()
    return any(fragment in normalized for fragment in _SENSITIVE_FRAGMENTS)


def redact(value: Any, *, key: str = "") -> Any:
    """Return a JSON-safe copy with sensitive keys masked at every depth."""
    if key and _is_sensitive(key):
        return REDACTED
    if isinstance(value, Mapping):
        return {str(item_key): redact(item, key=str(item_key)) for item_key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [redact(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


class JsonLinesFormatter(logging.Formatter):
    """Serialize one structured, redacted log record per line."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc)
        event = getattr(record, "event", None) or record.getMessage()
        output = {
            "timestamp": timestamp.isoformat(timespec="milliseconds").replace(
                "+00:00", "Z"
            ),
            "level": record.levelname,
            "event": event,
        }
        for key, value in record.__dict__.items():
            if key in _STANDARD_RECORD_KEYS or key in {"event", "message", "asctime"}:
                continue
            output[key] = redact(value, key=key)
        return json.dumps(redact(output), ensure_ascii=False, separators=(",", ":"))


def configure_json_logger(
    name: str,
    path: str | Path,
    *,
    level: str,
    max_bytes: int,
    backup_count: int,
    retention_days: int,
) -> logging.Logger:
    """Create a JSONL logger capped by total size and rotation age."""
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    _remove_expired_rotations(log_path, retention_days)
    bytes_per_file = max(1, max_bytes // (backup_count + 1))
    handler = RotatingFileHandler(
        log_path,
        maxBytes=bytes_per_file,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setFormatter(JsonLinesFormatter())

    logger = logging.getLogger(name)
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return logger


def _remove_expired_rotations(
    log_path: Path,
    retention_days: int,
    *,
    now_seconds: float | None = None,
) -> None:
    cutoff = (time.time() if now_seconds is None else now_seconds) - (
        retention_days * 24 * 60 * 60
    )
    for candidate in log_path.parent.glob(f"{log_path.name}.*"):
        if candidate.is_file() and candidate.stat().st_mtime < cutoff:
            candidate.unlink()
