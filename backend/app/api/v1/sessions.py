"""``/api/v1/sessions``: sesiones activas y revocación. El admin ve y cierra todas; un usuario, solo las suyas."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query, status

from app.api.deps import Context, CurrentSession, DbSession, SettingsDep
from app.api.v1.schemas import MAX_PAGE_SIZE, SessionOut, SessionPage
from app.domain.identity import auth, sessions

router = APIRouter(prefix="/sessions", tags=["sessions"])

_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"description": "No autenticado"},
    403: {"description": "Token CSRF no válido"},
}


@router.get("", response_model=SessionPage, summary="Listar sesiones activas", responses=_ERRORS)
def list_sessions(
    current: CurrentSession,
    db: DbSession,
    settings: SettingsDep,
    user_id: Annotated[int | None, Query(ge=1, description="Solo admin: sesiones de ese usuario")] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SessionPage:
    """Sesiones vigentes, la actividad más reciente primero. Un usuario que no es admin solo ve las suyas."""
    if current.user.role != "admin":
        user_id = current.user_id
    rows, total = sessions.list_sessions(db, settings, user_id=user_id, limit=limit, offset=offset)
    items = [
        SessionOut(
            id=s.id,
            user_id=s.user_id,
            username=s.user.username,
            created_at=s.created_at,
            last_seen_at=s.last_seen_at,
            expires_at=s.expires_at,
            ip=s.ip,
            user_agent=s.user_agent,
            current=s.id == current.id,
        )
        for s in rows
    ]
    return SessionPage(items=items, total=total)


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revocar sesión",
    responses={**_ERRORS, 404: {"description": "No existe o es de otro usuario"}},
)
def revoke_session(session_id: int, current: CurrentSession, db: DbSession, ctx: Context) -> None:
    """Cierra la sesión indicada de inmediato. Una sesión ajena da 404 si quien la pide no es admin."""
    auth.revoke_session(db, session_id, actor=current.user, ctx=ctx)
