"""``/api/v1/audit``: consulta del registro de auditoría (solo ``admin``)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import AwareDatetime

from app.api.deps import AdminUser, DbSession
from app.api.v1.schemas import MAX_PAGE_SIZE, AuditEntryOut, AuditPage
from app.domain.identity import audit

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get(
    "",
    response_model=AuditPage,
    summary="Consultar auditoría",
    responses={401: {"description": "No autenticado"}, 403: {"description": "Sin rol de administrador"}},
)
def list_audit(
    _: AdminUser,
    db: DbSession,
    action: Annotated[str | None, Query(max_length=64, description="Acción o prefijo, p. ej. `auth.`")] = None,
    actor_id: Annotated[int | None, Query(ge=1)] = None,
    actor: Annotated[str | None, Query(max_length=64, description="Nombre de usuario del autor")] = None,
    since: Annotated[AwareDatetime | None, Query(description="Desde (incluido), ISO 8601 con zona")] = None,
    until: Annotated[AwareDatetime | None, Query(description="Hasta (excluido), ISO 8601 con zona")] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AuditPage:
    """Eventos más recientes primero."""
    rows, total = audit.list_entries(
        db, action=action, actor_id=actor_id, actor=actor, since=since, until=until, limit=limit, offset=offset
    )
    return AuditPage(items=[AuditEntryOut.model_validate(e) for e in rows], total=total)
