"""Quitar rutas del contenedor de textos que ve el usuario (mensajes de error, ``run.log`` descargable).

Primero se sustituyen las raíces conocidas por una etiqueta (``/mnt/docs/2024/a.pdf`` → ``«Origen»/2024/a.pdf``);
después, cualquier otra ruta absoluta de las carpetas del sistema que quede (``/opt/venv/…``, ``/tmp/…``) se reduce a
``«ruta»``. Nunca se pasa texto de excepciones de terceros al usuario sin este paso.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from typing import Final

from app.core.logging import JsonFormatter

_ABSOLUTE: Final = re.compile(
    r"(?<![\w.«»/])/(?:mnt|data|workspace|models|tmp|opt|usr|app|root|home|proc|srv|var|etc|run)(?![\w.-])"
    r"(?:/[^\s'\"`:,;()\[\]{}<>]*)?"
)
REDACTED: Final = "«ruta»"


class PathRedactor:
    """Sustituye raíces conocidas por etiquetas y el resto de rutas absolutas del sistema por ``«ruta»``."""

    def __init__(self, roots: Iterable[tuple[str, str]]) -> None:
        # Las raíces más largas primero: una ruta se atribuye a la carpeta más concreta.
        cleaned = {root.rstrip("/") or "/": label for root, label in roots if root and root != "/"}
        self._roots = sorted(cleaned.items(), key=lambda item: -len(item[0]))

    def text(self, message: str) -> str:
        """``message`` sin rutas del contenedor."""
        for root, label in self._roots:
            message = re.sub(re.escape(root) + r"(?=/|\b|$)", label, message)
        return _ABSOLUTE.sub(REDACTED, message)


class RunLogFilter(logging.Filter):
    """Registros del ``run.log`` que se descarga: los de la aplicación y los avisos o errores de las librerías."""

    def filter(self, record: logging.LogRecord) -> bool:
        return record.name.startswith("app.") or record.levelno >= logging.WARNING


class RedactingJsonFormatter(JsonFormatter):
    """JSON como ``JsonFormatter``, con el mensaje sin rutas y sin trazas (solo el tipo de la excepción)."""

    def __init__(self, redactor: PathRedactor) -> None:
        super().__init__()
        self._redactor = redactor

    def format(self, record: logging.LogRecord) -> str:
        copy = logging.makeLogRecord(vars(record))
        copy.msg = self._redactor.text(record.getMessage())
        copy.args = None
        if record.exc_info and record.exc_info[0] is not None:
            copy.exc_type = record.exc_info[0].__name__
        copy.exc_info = None
        copy.exc_text = None
        return super().format(copy)
