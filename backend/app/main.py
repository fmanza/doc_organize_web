"""Fábrica de la aplicación FastAPI: monta ``/api`` y sirve el build del frontend con *fallback* de SPA."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import health
from app.api.v1 import router as v1_router
from app.core.config import Settings, get_settings
from app.core.errors import install_error_handlers, problem
from app.core.logging import configure_logging
from app.core.middleware import RequestMiddleware


def create_app(settings: Settings | None = None) -> FastAPI:
    """Crea la aplicación.

    Args:
        settings: Ajustes a usar; por defecto, los del entorno.

    Returns:
        Aplicación con ``/api/health``, ``/api/v1`` y, si existe ``static_dir``, la SPA.
    """
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="doc_organize_web",
        version=__version__,
        openapi_url="/api/openapi.json" if settings.environment != "production" else None,
        docs_url="/api/docs" if settings.environment == "development" else None,
        redoc_url=None,
    )
    install_error_handlers(app)
    app.add_middleware(RequestMiddleware)

    api = APIRouter(prefix="/api")
    api.include_router(health.router)
    api.include_router(v1_router)
    app.include_router(api)

    _mount_spa(app, settings.static_dir)
    return app


def _mount_spa(app: FastAPI, static_dir: Path) -> None:
    """Sirve ``static_dir`` y devuelve ``index.html`` en rutas del cliente; ``/api/*`` desconocido da 404."""
    index = static_dir / "index.html"
    if not index.is_file():
        return
    assets = static_dir / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")
    root = static_dir.resolve()

    @app.get("/{path:path}", include_in_schema=False, response_model=None)
    def spa(path: str) -> Response:
        if path == "api" or path.startswith("api/"):
            return problem(404, "Not Found")
        candidate = (root / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)
        return FileResponse(index)
