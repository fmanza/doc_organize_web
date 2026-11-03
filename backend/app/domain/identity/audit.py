"""Registro de auditoría de acciones de identidad y administración."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.request_context import current_tenant_id
from app.db.models import DEFAULT_TENANT_ID, AuditEntry, User


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
    PROJECT_CREATE: Final = "project.create"
    PROJECT_UPDATE: Final = "project.update"
    PROJECT_MEMBER_ADD: Final = "project.member_add"
    PROJECT_MEMBER_UPDATE: Final = "project.member_update"
    PROJECT_MEMBER_REMOVE: Final = "project.member_remove"
    PROJECT_HISTORY_CLEAR: Final = "project.history_clear"
    PROJECT_MOVE: Final = "project.move"
    PROJECT_DELETE: Final = "project.delete"
    SCAN_FOLDER_ADD: Final = "project.scan_folder_add"
    SCAN_FOLDER_REMOVE: Final = "project.scan_folder_remove"
    PROJECT_SCAN_FORCE: Final = "project.scan_force"
    DUPLICATE_MOVE: Final = "duplicate.move"
    DUPLICATE_COPY: Final = "duplicate.copy"
    DUPLICATE_APPLY: Final = "duplicate.apply"
    TAXONOMY_TEMPLATE_SAVE: Final = "taxonomy_template.save"
    TAXONOMY_TEMPLATE_DELETE: Final = "taxonomy_template.delete"
    PROJECT_TAXONOMY_MANIFEST_SAVE: Final = "project.taxonomy_manifest_save"
    PROJECT_CONTEXT_BUILD: Final = "project.context_build"
    PROJECT_CONTEXT_DELETE: Final = "project.context_delete"
    PROJECT_TAXONOMY_DRAFT: Final = "project.taxonomy_draft"
    AI_SETTINGS_UPDATE: Final = "ai_settings.update"
    RUN_ENQUEUE: Final = "run.enqueue"
    RUN_CANCEL: Final = "run.cancel"
    WORKER_CAPABILITIES_REFRESH: Final = "worker.capabilities_refresh"
    SESSION_REVOKE: Final = "session.revoke"
    SESSION_TENANT_SWITCH: Final = "session.tenant_switch"
    TENANT_CREATE: Final = "tenant.create"
    TENANT_UPDATE: Final = "tenant.update"
    TENANT_DELETE: Final = "tenant.delete"
    ROLE_CREATE: Final = "role.create"
    ROLE_UPDATE: Final = "role.update"
    ROLE_DELETE: Final = "role.delete"
    USER_MOVE: Final = "user.move"


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
    tenant_id: int | None = None,
) -> AuditEntry:
    """Añade un evento a la sesión de BD (lo confirma quien llama). ``details`` no debe contener secretos.

    El tenant es ``tenant_id``; si no, el de la petición (``db.info["tenant_id"]``, lo fija la dependencia de sesión),
    el del job en curso (``current_tenant_id``) o el del actor (Fase 9).
    """
    if tenant_id is None:
        scoped = db.info.get("tenant_id")
        tenant_id = scoped if isinstance(scoped, int) else current_tenant_id()
    if tenant_id is None and actor_id is not None:
        actor = db.get(User, actor_id)
        tenant_id = actor.tenant_id if actor is not None else None
    entry = AuditEntry(
        tenant_id=tenant_id if tenant_id is not None else DEFAULT_TENANT_ID,
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
    tenant_id: int,
    action: str | None,
    actor_id: int | None,
    actor: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int,
    offset: int,
) -> tuple[list[AuditEntry], int]:
    """Eventos del tenant, más recientes primero, filtrados por acción (prefijo), actor (id o nombre) y rango
    ``[since, until)``."""
    query = select(AuditEntry).where(AuditEntry.tenant_id == tenant_id)
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
