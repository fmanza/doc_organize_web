"""Comprobación de salud para Docker ``HEALTHCHECK`` y el frontend.

Pública: solo da estados agregados, nunca nombres ni rutas. Fases siguientes añaden el worker (F3) y los modelos (F4).
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from app import __version__
from app.db.session import get_engine, ping
from app.domain.locations.service import aggregate_status
from app.integrations.doc_organize import library_version

router = APIRouter(tags=["health"])

LocationsHealth = Literal["none", "ok", "degraded", "unavailable", "unknown"]


class HealthStatus(BaseModel):
    """Estado del servicio.

    Attributes:
        status: ``ok`` si ``config.db`` responde y doc_organize está instalado; ``degraded`` si no. Las ubicaciones no
            cuentan: una carpeta de red caída no hace que Docker reinicie la aplicación.
        version: Versión de doc_organize_web.
        doc_organize_version: Versión instalada de doc_organize.
        database: Estado de ``config.db``.
        locations: Peor estado del último sondeo de las ubicaciones (``none`` si no hay; ``unknown`` si no se pudo leer).
    """

    status: Literal["ok", "degraded"]
    version: str
    doc_organize_version: str | None
    database: Literal["ok", "error"]
    locations: LocationsHealth


def _locations_health(db_ok: bool) -> LocationsHealth:
    if not db_ok:
        return "unknown"
    try:
        with sessionmaker(bind=get_engine())() as db:
            return aggregate_status(db)  # type: ignore[return-value]
    except SQLAlchemyError:
        return "unknown"  # p. ej. antes de aplicar la migración 0003


@router.get(
    "/health",
    response_model=HealthStatus,
    summary="Estado del servicio",
    responses={503: {"model": HealthStatus, "description": "Servicio degradado"}},
)
def health(response: Response) -> HealthStatus:
    """Devuelve el estado de ``config.db``, de las ubicaciones y las versiones (503 si degradado)."""
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
        locations=_locations_health(db_ok),
    )
