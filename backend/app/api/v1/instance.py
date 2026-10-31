"""``/api/v1/instance``: datos de la instancia que cualquier sesión necesita (capacidades para las opciones de escaneo)."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.api.v1.schemas import CapabilitiesOut, InstanceCapabilities
from app.integrations.doc_organize import capabilities_cache, library_version

router = APIRouter(prefix="/instance", tags=["instance"])


@router.get(
    "/capabilities",
    response_model=InstanceCapabilities,
    summary="Capacidades de la instancia",
    responses={401: {"description": "No autenticado"}},
)
def get_capabilities(_: CurrentUser) -> InstanceCapabilities:
    """GPU, audio/vídeo y LibreOffice. ``pending`` mientras se calcula la primera vez (tarda varios segundos)."""
    snapshot = capabilities_cache.get()
    return InstanceCapabilities(
        status=snapshot.status,
        checked_at=snapshot.checked_at,
        capabilities=CapabilitiesOut(**asdict(snapshot.capabilities)) if snapshot.capabilities else None,
        doc_organize_version=library_version(),
    )
