"""Identificador de petición (``X-Request-ID``) disponible para los logs y los *problem details*."""

from __future__ import annotations

import logging
import re
import uuid
from contextvars import ContextVar, Token
from typing import Final

REQUEST_ID_HEADER: Final = "X-Request-ID"
_VALID: Final = re.compile(r"^[A-Za-z0-9._-]{8,64}$")

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def current_request_id() -> str | None:
    """``request_id`` de la petición en curso, o ``None`` fuera de una petición."""
    return _request_id.get()


def accept_or_generate(incoming: str | None) -> str:
    """Usa el ``X-Request-ID`` recibido si es válido (proxy o cliente); si no, genera uno nuevo.

    Un valor libre del cliente acabaría en los logs: solo se aceptan caracteres seguros y longitud acotada.
    """
    if incoming and _VALID.fullmatch(incoming):
        return incoming
    return uuid.uuid4().hex


def bind_request_id(value: str) -> Token[str | None]:
    """Fija el ``request_id`` del contexto; devuelve el token para restaurarlo con :func:`reset_request_id`."""
    return _request_id.set(value)


def reset_request_id(token: Token[str | None]) -> None:
    _request_id.reset(token)


class RequestIdFilter(logging.Filter):
    """Añade ``request_id`` a cada registro emitido dentro de una petición."""

    def filter(self, record: logging.LogRecord) -> bool:
        value = _request_id.get()
        if value is not None and not hasattr(record, "request_id"):
            record.request_id = value
        return True
