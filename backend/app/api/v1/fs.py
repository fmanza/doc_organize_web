"""``/api/v1/fs/browse``: explorador de carpetas dentro de una ubicación (sustituye a ``/api/fs/browse``).

Solo rutas relativas a la ubicación; nunca parte de ``Path.home()`` ni acepta rutas absolutas (ADR-007).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession, SettingsDep
from app.api.v1.schemas import MAX_FOLDER_PAGE, FolderEntry, FolderListing
from app.domain.locations import service
from app.domain.locations.service import FolderPage

router = APIRouter(prefix="/fs", tags=["filesystem"])

FS_ERRORS: dict[int | str, dict[str, Any]] = {
    400: {"description": "Ruta no válida (absoluta, UNC, con «..» o «\\»)"},
    401: {"description": "No autenticado"},
    404: {"description": "Ubicación o carpeta no encontrada (también si la ruta sale de la ubicación)"},
    503: {"description": "Ubicación no disponible"},
}


def listing(page: FolderPage, location_id: int | None) -> FolderListing:
    """Respuesta HTTP de una página de subcarpetas."""
    return FolderListing(
        location_id=location_id,
        path=page.path,
        parent=page.parent,
        items=[FolderEntry(name=name, path=path) for name, path in page.items()],
        total=page.total,
    )


@router.get("/browse", response_model=FolderListing, summary="Explorar carpetas de una ubicación", responses=FS_ERRORS)
def browse(
    _: CurrentUser,
    db: DbSession,
    settings: SettingsDep,
    location_id: Annotated[int, Query(ge=1)],
    path: Annotated[str, Query(max_length=4096, description="Ruta relativa con «/»; vacía = la raíz")] = "",
    limit: Annotated[int, Query(ge=1, le=MAX_FOLDER_PAGE)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> FolderListing:
    """Subcarpetas de ``path`` dentro de la ubicación, ordenadas por nombre."""
    location = service.get_location(db, location_id)
    page = service.browse(location, path, settings=settings, limit=limit, offset=offset)
    return listing(page, location.id)
