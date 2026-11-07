"""``/api/v1/locations``: ubicaciones registradas (ADR-007). Las ve cualquier sesión; solo un admin las gestiona.

La ruta del contenedor (``container_path``) solo aparece en las respuestas para administradores.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query, status

from app.api.deps import Context, CurrentUser, DbSession, InstanceAdmin, SettingsDep
from app.api.v1.listing import LocationSort, OrderQuery, SearchQuery, listing
from app.api.v1.schemas import (
    MAX_PAGE_SIZE,
    LocationCreate,
    LocationOut,
    LocationPage,
    LocationPublic,
    LocationUpdate,
)
from app.db.models import Location, User
from app.domain.locations import service
from app.domain.locations.service import LocationChanges

router = APIRouter(prefix="/locations", tags=["locations"])

_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"description": "No autenticado"},
    403: {"description": "Sin rol de administrador o token CSRF no válido"},
}
_404: dict[int | str, dict[str, Any]] = {404: {"description": "No existe"}}


def _out(location: Location, user: User) -> LocationOut | LocationPublic:
    model = LocationOut if user.is_instance_admin else LocationPublic
    return model.model_validate(location)


@router.get("", response_model=LocationPage, summary="Listar ubicaciones", responses=_ERRORS)
def list_locations(
    user: CurrentUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    q: SearchQuery = None,
    sort: Annotated[LocationSort | None, Query(description="Columna por la que ordenar")] = None,
    order: OrderQuery = "asc",
) -> LocationPage:
    """Ubicaciones (por nombre si no se pide otro orden), con su último estado."""
    rows, total = service.list_locations(
        db, tenant_id=user.scope_tenant_id, limit=limit, offset=offset, listing=listing(q, sort, order)
    )
    return LocationPage(items=[_out(row, user) for row in rows], total=total)


@router.post(
    "",
    response_model=LocationOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar ubicación",
    responses={
        **_ERRORS,
        400: {
            "description": "Carpeta no válida (fuera de la raíz, inexistente o solapada) o patrones no válidos "
            "(invalid_ignore_patterns)"
        },
        409: {"description": "Nombre o carpeta ya registrados"},
    },
)
def create_location(
    body: LocationCreate, admin: InstanceAdmin, db: DbSession, settings: SettingsDep, ctx: Context
) -> LocationOut:
    """Registra una carpeta de ``DOW_LOCATIONS_ROOT`` como ubicación y la sondea; con ``ignore_patterns``, los nombres
    que no escanea ningún proyecto (solo ubicaciones de origen)."""
    location = service.create_location(
        db,
        name=body.name,
        path=body.path,
        display_path=body.display_path,
        kind=body.kind,
        usage=body.usage,
        access=body.access,
        settings=settings,
        actor=admin,
        ctx=ctx,
        tenant_id=admin.scope_tenant_id,
        ignore_patterns=body.ignore_patterns,
    )
    return LocationOut.model_validate(location)


@router.get(
    "/{location_id}",
    response_model=LocationOut | LocationPublic,
    summary="Ver ubicación",
    responses={**_ERRORS, **_404},
)
def get_location(location_id: int, user: CurrentUser, db: DbSession) -> LocationOut | LocationPublic:
    """Detalle de una ubicación."""
    return _out(service.get_location(db, location_id, tenant_id=user.scope_tenant_id), user)


@router.patch(
    "/{location_id}",
    response_model=LocationOut,
    summary="Editar ubicación",
    responses={
        **_ERRORS,
        **_404,
        400: {"description": "Patrones no válidos (invalid_ignore_patterns)"},
        409: {"description": "Nombre ya registrado"},
    },
)
def update_location(
    location_id: int, body: LocationUpdate, admin: InstanceAdmin, db: DbSession, settings: SettingsDep, ctx: Context
) -> LocationOut:
    """Cambia nombre, texto visible, tipo, uso, acceso o patrones de nombre que no se escanean (la carpeta del
    contenedor no se puede cambiar). Los patrones afectan a todos los proyectos que leen de la ubicación: con «forzar
    reconversión», lo ya convertido que encaje se borra."""
    location = service.get_location(db, location_id, tenant_id=admin.scope_tenant_id)
    changes = LocationChanges(**body.model_dump(exclude_unset=True))
    return LocationOut.model_validate(
        service.update_location(db, location, changes, settings=settings, actor=admin, ctx=ctx)
    )


@router.delete(
    "/{location_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Borrar ubicación",
    responses={**_ERRORS, **_404, 409: {"description": "Algún proyecto la usa"}},
)
def delete_location(location_id: int, admin: InstanceAdmin, db: DbSession, ctx: Context) -> None:
    """Quita la ubicación del registro; la carpeta y su contenido no se tocan."""
    location = service.get_location(db, location_id, tenant_id=admin.scope_tenant_id)
    service.delete_location(db, location, actor=admin, ctx=ctx)


@router.post(
    "/{location_id}/probe",
    response_model=LocationOut,
    summary="Comprobar ubicación",
    responses={**_ERRORS, **_404},
)
def probe_location(
    location_id: int, admin: InstanceAdmin, db: DbSession, settings: SettingsDep, ctx: Context
) -> LocationOut:
    """Sondea la ubicación (existencia, lectura, latencia, espacio y escritura si es ``rw``) y guarda el estado."""
    location = service.get_location(db, location_id, tenant_id=admin.scope_tenant_id)
    return LocationOut.model_validate(service.probe_location(db, location, settings=settings, actor=admin, ctx=ctx))
