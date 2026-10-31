"""Registro de auditoría de acciones de identidad y administración."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import AuditEntry, User


class AuditAction:
    """Acciones auditadas (valor de ``audit_log.action``)."""

    LOGIN: Final = "auth.login"
    LOCKOUT: Final = "auth.lockout"
    LOGOUT: Final = "auth.logout"
    PASSWORD_CHANGE: Final = "auth.password_change"  # noqa: S105 (nombre de acción)
    USER_CREATE: Final = "user.create"
    USER_UPDATE: Final = "user.update"
    USER_DEACTIVATE: Final = "user.deactivate"
    USER_REACTIVATE: Final = "user.reactivate"
    USER_PASSWORD_RESET: Final = "user.password_reset"  # noqa: S105 (nombre de acción)
    USER_UNLOCK: Final = "user.unlock"
    SETTINGS_UPDATE: Final = "settings.update"
    LOCATION_CREATE: Final = "location.create"
    LOCATION_UPDATE: Final = "location.update"
    LOCATION_DELETE: Final = "location.delete"
    LOCATION_PROBE: Final = "location.probe"
    SESSION_REVOKE: Final = "session.revoke"


@dataclass(frozen=True)
class RequestContext:
    """Origen de la acción, para auditoría y sesiones.

    Attributes:
        ip: IP del cliente (la que entrega uvicorn con ``--proxy-headers``).
        user_agent: Cabecera ``User-Agent``, truncada a 255 caracteres.
    """

    ip: str | None = None
    user_agent: str | None = None

    def __post_init__(self) -> None:
        if self.user_agent is not None:
            object.__setattr__(self, "user_agent", self.user_agent[:255])


CLI_CONTEXT = RequestContext(ip=None, user_agent="cli")


def record(
    db: Session,
    *,
    action: str,
    ctx: RequestContext,
    actor_id: int | None,
    outcome: str = "success",
    target_type: str | None = None,
    target_id: int | str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditEntry:
    """Añade un evento a la sesión de BD (lo confirma quien llama). ``details`` no debe contener secretos."""
    entry = AuditEntry(
        action=action,
        outcome=outcome,
        actor_user_id=actor_id,
        target_type=target_type,
        target_id=None if target_id is None else str(target_id),
        ip=ctx.ip,
        details=details,
    )
    db.add(entry)
    return entry


def list_entries(
    db: Session,
    *,
    action: str | None,
    actor_id: int | None,
    actor: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int,
    offset: int,
) -> tuple[list[AuditEntry], int]:
    """Eventos más recientes primero, filtrados por acción (prefijo), actor (id o nombre) y rango ``[since, until)``."""
    query = select(AuditEntry)
    if action:
        query = query.where(AuditEntry.action.startswith(action, autoescape=True))
    if actor_id is not None:
        query = query.where(AuditEntry.actor_user_id == actor_id)
    if actor:
        query = query.where(AuditEntry.actor_user_id.in_(select(User.id).where(User.username == actor.strip().lower())))
    if since is not None:
        query = query.where(AuditEntry.ts >= since)
    if until is not None:
        query = query.where(AuditEntry.ts < until)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(AuditEntry.id.desc()).limit(limit).offset(offset)).all()
    return list(rows), total
