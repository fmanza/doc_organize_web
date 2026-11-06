"""``/api/v1/audit``: consulta del registro de auditoría (``audit.read``) y su purga por fechas (solo el admin de
instancia, web 1.2.0)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import AwareDatetime

from app.api.deps import AuditReader, Context, DbSession, InstanceAdmin
from app.api.v1.listing import AuditSort, OrderQuery, SearchQuery, listing
from app.api.v1.schemas import MAX_PAGE_SIZE, AuditEntryOut, AuditPage, AuditPurgeIn, AuditPurgeOut
from app.domain.identity import audit

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get(
    "",
    response_model=AuditPage,
    summary="Consultar auditoría",
    responses={401: {"description": "No autenticado"}, 403: {"description": "Sin permiso audit.read"}},
)
def list_audit(
    reader: AuditReader,
    db: DbSession,
    action: Annotated[str | None, Query(max_length=64, description="Acción o prefijo, p. ej. `auth.`")] = None,
    actor_id: Annotated[int | None, Query(ge=1)] = None,
    actor: Annotated[str | None, Query(max_length=64, description="Nombre de usuario del autor")] = None,
    since: Annotated[AwareDatetime | None, Query(description="Desde (incluido), ISO 8601 con zona")] = None,
    until: Annotated[AwareDatetime | None, Query(description="Hasta (excluido), ISO 8601 con zona")] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    q: SearchQuery = None,
    sort: Annotated[AuditSort | None, Query(description="Columna por la que ordenar")] = None,
    order: OrderQuery = "asc",
) -> AuditPage:
    """Eventos del tenant activo, más recientes primero."""
    rows, total = audit.list_entries(
        db,
        tenant_id=reader.scope_tenant_id,
        action=action,
        actor_id=actor_id,
        actor=actor,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
        listing=listing(q, sort, order),
    )
    return AuditPage(items=[AuditEntryOut.model_validate(e) for e in rows], total=total)


@router.post(
    "/purge",
    response_model=AuditPurgeOut,
    summary="Borrar auditoría por fechas",
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "No es administrador de la instancia o token CSRF no válido"},
        409: {"description": "Las entradas del rango cambiaron desde la vista previa (`purge_changed`)"},
        422: {"description": "Rango vacío o con entradas de hoy (`purge_range`)"},
    },
)
def purge_audit(body: AuditPurgeIn, admin: InstanceAdmin, db: DbSession, ctx: Context) -> AuditPurgeOut:
    """Cuenta (``dry_run``) o borra las entradas del tenant activo en ``[since, until)``; el borrado se audita."""
    result = audit.purge(
        db,
        tenant_id=admin.scope_tenant_id,
        since=body.since,
        until=body.until,
        dry_run=body.dry_run,
        confirm_count=body.confirm_count,
        actor=admin,
        ctx=ctx,
    )
    return AuditPurgeOut(matched=result.matched, deleted=result.deleted)
