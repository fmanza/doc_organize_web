"""Roles de un tenant con permisos de administración (WB-9.2, ADR-013).

Cada tenant tiene dos roles base (``builtin``: «Administrador» y «Usuario») que no se borran ni cambian de permisos.
Los personalizados los gestiona quien tiene ``roles.manage``, y nadie da un permiso que no tiene (salvo el admin de
instancia, que los tiene todos).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import TenantRole, User
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction, RequestContext
from app.domain.tenancy.errors import (
    InvalidPermissionError,
    PermissionEscalationError,
    RoleBuiltinError,
    RoleInUseError,
    RoleNameTakenError,
    RoleNotFoundError,
)
from app.domain.tenancy.permissions import BUILTIN_ROLES, BuiltinRole, normalize, unknown


@dataclass(frozen=True)
class RoleView:
    role: TenantRole
    users: int


def create_builtin_roles(db: Session, tenant_id: int) -> None:
    """Crea los roles base del tenant (sin confirmar)."""
    for key, (name, permissions) in BUILTIN_ROLES.items():
        db.add(TenantRole(tenant_id=tenant_id, name=name, builtin=key, permissions=normalize(permissions)))


def builtin_role(db: Session, tenant_id: int, key: BuiltinRole) -> TenantRole:
    """Rol base ``key`` del tenant (la migración y el alta de tenants lo garantizan)."""
    role = db.scalar(select(TenantRole).where(TenantRole.tenant_id == tenant_id, TenantRole.builtin == key))
    if role is None:  # pragma: no cover - lo crean la migración 0009 y create_tenant
        raise RoleNotFoundError()
    return role


def get_role(db: Session, role_id: int, *, tenant_id: int) -> TenantRole:
    """Rol del tenant.

    Raises:
        RoleNotFoundError: No existe o es de otro tenant (no se revela cuál).
    """
    role = db.get(TenantRole, role_id)
    if role is None or role.tenant_id != tenant_id:
        raise RoleNotFoundError()
    return role


def _users(db: Session, role_id: int) -> int:
    return db.scalar(select(func.count()).where(User.role_id == role_id)) or 0


def list_roles(db: Session, *, tenant_id: int) -> list[RoleView]:
    """Roles del tenant: los base primero y después por nombre, con su número de usuarios."""
    roles = db.scalars(
        select(TenantRole)
        .where(TenantRole.tenant_id == tenant_id)
        .order_by(TenantRole.builtin.is_(None), func.lower(TenantRole.name))
    )
    rows = db.execute(select(User.role_id, func.count()).where(User.tenant_id == tenant_id).group_by(User.role_id))
    counts = {int(role_id): int(count) for role_id, count in rows}
    return [RoleView(role, counts.get(role.id, 0)) for role in roles]


def check_grant(actor: User, permissions: list[str]) -> None:
    """``actor`` puede dar ``permissions``.

    Raises:
        PermissionEscalationError: Alguno no lo tiene.
    """
    if actor.is_instance_admin:
        return
    missing = set(permissions) - set(actor.permissions)
    if missing:
        raise PermissionEscalationError(f"No tienes: {', '.join(sorted(missing))}")


def _validated(permissions: list[str]) -> list[str]:
    bad = unknown(permissions)
    if bad:
        raise InvalidPermissionError(f"Desconocidos: {', '.join(bad)}")
    return list(normalize(permissions))


def _name_taken(db: Session, tenant_id: int, name: str, *, exclude: int | None = None) -> bool:
    query = select(TenantRole.id).where(
        TenantRole.tenant_id == tenant_id, func.lower(TenantRole.name) == name.strip().lower()
    )
    if exclude is not None:
        query = query.where(TenantRole.id != exclude)
    return db.scalar(query) is not None


def create_role(
    db: Session, *, tenant_id: int, name: str, permissions: list[str], actor: User, ctx: RequestContext
) -> TenantRole:
    """Crea un rol personalizado y lo audita.

    Raises:
        InvalidPermissionError, PermissionEscalationError, RoleNameTakenError.
    """
    granted = _validated(permissions)
    check_grant(actor, granted)
    if _name_taken(db, tenant_id, name):
        raise RoleNameTakenError()
    role = TenantRole(tenant_id=tenant_id, name=name.strip(), permissions=granted, created_by=actor.id)
    db.add(role)
    db.flush()
    audit.record(
        db,
        action=AuditAction.ROLE_CREATE,
        ctx=ctx,
        actor_id=actor.id,
        target_type="role",
        target_id=role.id,
        details={"name": role.name, "permissions": granted},
        tenant_id=tenant_id,
    )
    db.commit()
    return role


def update_role(
    db: Session,
    role: TenantRole,
    *,
    name: str | None,
    permissions: list[str] | None,
    actor: User,
    ctx: RequestContext,
) -> TenantRole:
    """Renombra o cambia los permisos de un rol personalizado (los base solo se renombran: no).

    Quitar permisos cierra las sesiones de quienes tienen el rol (dejan de valer de inmediato).

    Raises:
        RoleBuiltinError, InvalidPermissionError, PermissionEscalationError, RoleNameTakenError.
    """
    from app.domain.identity.sessions import revoke_user_sessions

    if role.builtin is not None:
        raise RoleBuiltinError()
    changes: dict[str, object] = {}
    if name is not None and name.strip() != role.name:
        if _name_taken(db, role.tenant_id, name, exclude=role.id):
            raise RoleNameTakenError()
        changes["name"] = [role.name, name.strip()]
        role.name = name.strip()
    if permissions is not None:
        granted = _validated(permissions)
        check_grant(actor, sorted(set(granted) ^ set(role.permissions or [])))  # ni dar ni quitar lo que no tienes
        removed = set(role.permissions or []) - set(granted)
        if granted != list(role.permissions or []):
            changes["permissions"] = [list(role.permissions or []), granted]
            role.permissions = granted
        if removed:
            for user_id in db.scalars(select(User.id).where(User.role_id == role.id)):
                revoke_user_sessions(db, user_id)
    if changes:
        audit.record(
            db,
            action=AuditAction.ROLE_UPDATE,
            ctx=ctx,
            actor_id=actor.id,
            target_type="role",
            target_id=role.id,
            details=changes,
            tenant_id=role.tenant_id,
        )
    db.commit()
    return role


def delete_role(db: Session, role: TenantRole, *, actor: User, ctx: RequestContext) -> None:
    """Borra un rol personalizado sin usuarios.

    Raises:
        RoleBuiltinError, RoleInUseError, PermissionEscalationError.
    """
    if role.builtin is not None:
        raise RoleBuiltinError()
    if _users(db, role.id):
        raise RoleInUseError("Asigna otro rol a sus usuarios antes de borrarlo.")
    check_grant(actor, list(role.permissions or []))
    audit.record(
        db,
        action=AuditAction.ROLE_DELETE,
        ctx=ctx,
        actor_id=actor.id,
        target_type="role",
        target_id=role.id,
        details={"name": role.name},
        tenant_id=role.tenant_id,
    )
    db.delete(role)
    db.commit()
