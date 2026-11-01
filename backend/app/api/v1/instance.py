"""``/api/v1/instance``: datos de la instancia que cualquier sesión necesita (capacidades para las opciones de escaneo)."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession, SettingsDep
from app.api.v1.schemas import CapabilitiesOut, InstanceCapabilities, ScanOptionsAvailability
from app.domain.runs import workers
from app.domain.scan.options import available_options
from app.integrations.doc_organize import library_version

router = APIRouter(prefix="/instance", tags=["instance"])


@router.get(
    "/capabilities",
    response_model=InstanceCapabilities,
    summary="Capacidades de la instancia",
    responses={401: {"description": "No autenticado"}},
)
def get_capabilities(_: CurrentUser, db: DbSession, settings: SettingsDep) -> InstanceCapabilities:
    """GPU, audio/vídeo, LibreOffice y modelos según los workers (los que convierten); colas con algún worker vivo y
    opciones de escaneo disponibles."""
    view = workers.capabilities(db, settings)
    return InstanceCapabilities(
        status=view.status,
        checked_at=view.checked_at,
        capabilities=CapabilitiesOut(**view.capabilities) if view.capabilities else None,
        queues=view.queues,
        doc_organize_version=library_version(),
        scan_options=ScanOptionsAvailability(**available_options(db, settings)),
    )
