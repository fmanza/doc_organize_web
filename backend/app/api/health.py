"""Comprobación de salud para Docker ``HEALTHCHECK`` y el frontend.

Pública: solo da estados agregados, nunca nombres ni rutas. La Fase 4 añadirá los modelos.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from app import __version__
from app.core.config import get_settings
from app.db.session import get_engine, ping
from app.domain.locations.service import aggregate_status
from app.domain.runs import workers
from app.integrations.doc_organize import library_version

router = APIRouter(tags=["health"])

LocationsHealth = Literal["none", "ok", "degraded", "unavailable", "unknown"]
WorkerHealth = Literal["none", "ok", "stale", "unknown"]


class HealthStatus(BaseModel):
    """Estado del servicio.

    Attributes:
        status: ``ok`` si ``config.db`` responde y doc_organize está instalado; ``degraded`` si no. Las ubicaciones no
            cuentan: una carpeta de red caída no hace que Docker reinicie la aplicación.
        version: Versión de doc_organize_web.
        doc_organize_version: Versión instalada de doc_organize.
        database: Estado de ``config.db``.
        locations: Peor estado del último sondeo de las ubicaciones (``none`` si no hay; ``unknown`` si no se pudo leer).
        worker: ``ok`` si algún worker late, ``stale`` si solo hay caídos, ``none`` si no hay ninguno. Tampoco cuenta
            para ``status``: sin worker la API sigue sirviendo (los runs esperan en cola).
    """

    status: Literal["ok", "degraded"]
    version: str
    doc_organize_version: str | None
    database: Literal["ok", "error"]
    locations: LocationsHealth
    worker: WorkerHealth


def _aggregates(db_ok: bool) -> tuple[LocationsHealth, WorkerHealth]:
    if not db_ok:
        return "unknown", "unknown"
    try:
        with sessionmaker(bind=get_engine())() as db:
            return aggregate_status(db), workers.health(db, get_settings())  # type: ignore[return-value]
    except SQLAlchemyError:
        return "unknown", "unknown"  # p. ej. antes de aplicar las migraciones


@router.get(
    "/health",
    response_model=HealthStatus,
    summary="Estado del servicio",
    responses={503: {"model": HealthStatus, "description": "Servicio degradado"}},
)
def health(response: Response) -> HealthStatus:
    """Devuelve el estado de ``config.db``, de las ubicaciones, del worker y las versiones (503 si degradado)."""
    db_ok = ping(get_engine())
    lib = library_version()
    status: Literal["ok", "degraded"] = "ok" if db_ok and lib else "degraded"
    if status == "degraded":
        response.status_code = 503
    locations, worker = _aggregates(db_ok)
    return HealthStatus(
        status=status,
        version=__version__,
        doc_organize_version=lib,
        database="ok" if db_ok else "error",
        locations=locations,
        worker=worker,
    )
