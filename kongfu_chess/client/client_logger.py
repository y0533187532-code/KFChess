"""Structured client event logging helpers."""

from __future__ import annotations

import logging
from typing import Any


class ClientEventLogger:
    """Emit redacted JSONL events when a production logger is configured."""

    def __init__(self, logger: logging.Logger | None):
        self._logger = logger

    def event(self, name: str, **fields: Any) -> None:
        if self._logger is None:
            return
        self._logger.info(name, extra={"event": name, **fields})
