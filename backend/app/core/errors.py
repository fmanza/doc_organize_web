"""Errores de la API en formato *problem details* (RFC 9457).

Los mensajes que llegan al cliente nunca incluyen el texto de excepciones de doc_organize, Docling ni del sistema de
ficheros: pueden contener rutas del contenedor o datos de los documentos. El detalle va al log, solo con el tipo de
la excepción (ver ``security.instructions.md``).
"""

from __future__ import annotations

import logging
from typing import ClassVar

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.request_context import current_request_id

PROBLEM_JSON = "application/problem+json"

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Error de negocio con estado HTTP; las capas de dominio lo especializan sin depender de FastAPI.

    Attributes:
        status: Código HTTP de la respuesta.
        title: Título del *problem details*.
        detail: Explicación para el usuario (nunca texto de excepciones de terceros).
        code: Código estable para que el cliente distinga casos con el mismo estado (p. ej. ``write_locked``).
    """

    status: ClassVar[int] = 400
    title: ClassVar[str] = "Petición no válida"
    code: ClassVar[str | None] = None

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(detail or self.title)
        self.detail = detail


def problem(status: int, title: str, detail: str | None = None, **extra: object) -> JSONResponse:
    """Respuesta ``application/problem+json`` con el ``request_id`` de la petición si lo hay."""
    body: dict[str, object] = {"type": "about:blank", "title": title, "status": status}
    if detail:
        body["detail"] = detail
    request_id = current_request_id()
    if request_id:
        body["request_id"] = request_id
    body.update(extra)
    return JSONResponse(body, status_code=status, media_type=PROBLEM_JSON)


def install_error_handlers(app: FastAPI) -> None:
    """Registra los handlers que convierten cualquier error en *problem details*."""

    @app.exception_handler(AppError)
    async def _app(_: Request, exc: AppError) -> JSONResponse:
        if exc.code:
            return problem(exc.status, exc.title, exc.detail, code=exc.code)
        return problem(exc.status, exc.title, exc.detail)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return problem(exc.status_code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
        return problem(422, "Datos de entrada no válidos", errors=errors)

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Error no controlado", extra={"path": request.url.path, "exc_type": type(exc).__name__})
        return problem(500, "Error interno")
