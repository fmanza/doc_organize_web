"""Comprobación de salud para Docker ``HEALTHCHECK`` y el frontend.

Fases siguientes añaden el estado del worker (F3), de las ubicaciones (F2) y de los modelos (F4).
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel

from app import __version__
from app.db.session import get_engine, ping
from app.integrations.doc_organize import library_version

router = APIRouter(tags=["health"])


class HealthStatus(BaseModel):
    """Estado del servicio.

    Attributes:
        status: ``ok`` si ``config.db`` responde y doc_organize está instalado; ``degraded`` si no.
        version: Versión de doc_organize_web.
        doc_organize_version: Versión instalada de doc_organize.
        database: Estado de ``config.db``.
    """

    status: Literal["ok", "degraded"]
    version: str
    doc_organize_version: str | None
    database: Literal["ok", "error"]


@router.get(
    "/health",
    response_model=HealthStatus,
    summary="Estado del servicio",
    responses={503: {"model": HealthStatus, "description": "Servicio degradado"}},
)
def health(response: Response) -> HealthStatus:
    """Devuelve el estado de ``config.db`` y las versiones de la aplicación y de doc_organize (503 si degradado)."""
    db_ok = ping(get_engine())
    lib = library_version()
    status: Literal["ok", "degraded"] = "ok" if db_ok and lib else "degraded"
    if status == "degraded":
        response.status_code = 503
    return HealthStatus(
        status=status,
        version=__version__,
        doc_organize_version=lib,
        database="ok" if db_ok else "error",
    )
