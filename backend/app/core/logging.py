"""Logging estructurado (una línea JSON por registro) para la API y el worker."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import ClassVar

from app.core.request_context import RequestIdFilter


class JsonFormatter(logging.Formatter):
    """Formatea cada registro como un objeto JSON con nivel, logger, mensaje, ``extra`` y excepción si la hay."""

    _RESERVED: ClassVar[frozenset[str]] = frozenset(vars(logging.makeLogRecord({})))

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        payload.update({k: v for k, v in vars(record).items() if k not in self._RESERVED and not k.startswith("_")})
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str) -> None:
    """Sustituye los handlers del logger raíz por uno a stdout en JSON con ``request_id``."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestIdFilter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
