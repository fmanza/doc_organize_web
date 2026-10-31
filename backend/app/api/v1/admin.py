"""``/api/v1/admin``: ajustes administrables (ADR-012), montajes disponibles y refresco de capacidades (solo admin)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query, status

from app.api.deps import AdminUser, Context, DbSession, SettingsDep
from app.api.v1.fs import FS_ERRORS, listing
from app.api.v1.schemas import MAX_FOLDER_PAGE, FolderListing, SettingOut, SettingsPage, SettingsUpdate
from app.core.config import get_settings
from app.domain.locations import service as locations
from app.domain.settings import service as settings_service
from app.domain.settings.service import SettingView
from app.integrations.doc_organize import capabilities_cache

router = APIRouter(prefix="/admin", tags=["admin"])

_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"description": "No autenticado"},
    403: {"description": "Sin rol de administrador o token CSRF no válido"},
}


def _page(views: list[SettingView]) -> SettingsPage:
    return SettingsPage(items=[SettingOut(key=v.key, value=v.value, default=v.default, source=v.source) for v in views])


@router.get("/settings", response_model=SettingsPage, summary="Ver ajustes administrables", responses=_ERRORS)
def list_settings(_: AdminUser, db: DbSession) -> SettingsPage:
    """Ajustes con su valor efectivo, el de la variable ``DOW_*`` (o por defecto) y su origen."""
    return _page(settings_service.list_settings(db, get_settings()))


@router.patch(
    "/settings",
    response_model=SettingsPage,
    summary="Cambiar ajustes administrables",
    responses={**_ERRORS, 400: {"description": "Ajuste desconocido"}, 422: {"description": "Valor no válido"}},
)
def update_settings(body: SettingsUpdate, admin: AdminUser, db: DbSession, ctx: Context) -> SettingsPage:
    """Aplica los cambios sin reiniciar; ``null`` devuelve el ajuste al valor de la variable o por defecto."""
    return _page(settings_service.update_settings(db, body.values, settings=get_settings(), actor=admin, ctx=ctx))


@router.get(
    "/mounts",
    response_model=FolderListing,
    summary="Explorar la raíz de ubicaciones",
    responses={**FS_ERRORS, **_ERRORS},
)
def browse_mounts(
    _: AdminUser,
    settings: SettingsDep,
    path: Annotated[str, Query(max_length=4096, description="Ruta relativa a DOW_LOCATIONS_ROOT")] = "",
    limit: Annotated[int, Query(ge=1, le=MAX_FOLDER_PAGE)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> FolderListing:
    """Subcarpetas bajo ``DOW_LOCATIONS_ROOT`` para elegir la carpeta de una ubicación nueva."""
    return listing(locations.browse_mounts(path, settings=settings, limit=limit, offset=offset), None)


@router.post(
    "/capabilities/refresh",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Volver a comprobar las capacidades",
    responses=_ERRORS,
)
def refresh_capabilities(_: AdminUser) -> None:
    """Lanza en segundo plano un nuevo sondeo de capacidades (si no hay uno en curso)."""
    capabilities_cache.refresh()
