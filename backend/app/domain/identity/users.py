"""Administración de usuarios: alta, edición, desactivación y reactivación (sin borrado físico).

Desde la Fase 9 cada usuario pertenece a un tenant y tiene un rol de ese tenant (``role_id``); ``is_instance_admin``
da lo que es del servidor. Las consultas reciben el tenant (ADR-013) y las salvaguardas impiden quedarse sin admin de
instancia o sin quien gestione los usuarios de un tenant, y dar permisos que uno no tiene.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import DEFAULT_TENANT_ID, ProjectMember, TenantRole, User, utcnow
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction, RequestContext
from app.domain.identity.errors import (
    LastAdminError,
    SelfModificationError,
    UsernameTakenError,
    UserNotFoundError,
)
from app.domain.identity.passwords import check_policy, hash_password
from app.domain.identity.sessions import revoke_user_sessions
from app.domain.listing import ListQuery, apply_search, apply_sort
from app.domain.tenancy import roles as tenant_roles
from app.domain.tenancy.errors import LastTenantManagerError, PermissionEscalationError
from app.domain.tenancy.tenants import get_tenant

USERS_MANAGE = "users.manage"


def normalize_username(username: str) -> str:
    """Los nombres de usuario no distinguen mayúsculas."""
    return username.strip().lower()


@dataclass(frozen=True)
class UserChanges:
    """Cambios de un ``PATCH``; ``None`` significa «sin cambio»."""

    display_name: str | None = None
    role_id: int | None = None
    is_instance_admin: bool | None = None
    tenant_id: int | None = None
    is_active: bool | None = None
    password: str | None = None
    unlock: bool = False


def get_user(db: Session, user_id: int, *, tenant_id: int | None) -> User:
    """Usuario por id, del tenant ``tenant_id`` (``None``: de cualquiera, solo para el admin de instancia).

    Raises:
        UserNotFoundError: No existe o es de otro tenant (no se revela cuál).
    """
    user = db.get(User, user_id)
    if user is None or (tenant_id is not None and user.tenant_id != tenant_id):
        raise UserNotFoundError()
    return user


def get_by_username(db: Session, username: str) -> User | None:
    """Usuario por nombre (normalizado; único en la instancia) o ``None``."""
    return db.scalar(select(User).where(User.username == normalize_username(username)))


def list_users(
    db: Session, *, tenant_id: int, q: str | None, limit: int, offset: int, listing: ListQuery | None = None
) -> tuple[list[User], int]:
    """Usuarios del tenant (por nombre de usuario si no se pide otro orden), filtrados por texto en usuario, nombre
    visible o rol."""
    listing = listing or ListQuery()
    query = select(User).join(TenantRole, TenantRole.id == User.role_id).where(User.tenant_id == tenant_id)
    query = apply_search(query, q or listing.q, [User.username, User.display_name, TenantRole.name])
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    columns = {
        "username": User.username,
        "display_name": func.lower(User.display_name),
        "role": func.lower(TenantRole.name),
        "status": User.is_active,
        "created_at": User.created_at,
    }
    query = apply_sort(query, listing, columns, default=[User.username], tiebreak=User.id)
    rows = db.scalars(query.limit(limit).offset(offset)).all()
    return list(rows), total


def lookup_users(db: Session, *, tenant_id: int, q: str, limit: int = 20) -> list[User]:
    """Usuarios **activos** del tenant cuyo usuario o nombre visible empieza por ``q`` (para invitar a un proyecto)."""
    prefix = q.strip().lower()
    if not prefix:
        return []
    query = (
        select(User)
        .where(
            User.tenant_id == tenant_id,
            User.is_active.is_(True),
            or_(
                User.username.startswith(prefix, autoescape=True),
                func.lower(User.display_name).startswith(prefix, autoescape=True),
            ),
        )
        .order_by(User.username)
        .limit(limit)
    )
    return list(db.scalars(query))


def _active_instance_admins(db: Session) -> int:
    return db.scalar(select(func.count()).where(User.is_instance_admin.is_(True), User.is_active.is_(True))) or 0


def _managers(db: Session, tenant_id: int, *, excluding: int) -> int:
    """Usuarios activos del tenant (sin ``excluding``) con ``users.manage``."""
    rows = db.execute(
        select(TenantRole.permissions)
        .join(User, User.role_id == TenantRole.id)
        .where(User.tenant_id == tenant_id, User.is_active.is_(True), User.id != excluding)
    )
    return sum(1 for (permissions,) in rows if USERS_MANAGE in (permissions or []))


def check_can_manage(actor: User, target: User) -> None:
    """``actor`` tiene todo lo que tiene ``target``: si no, gestionarlo (p. ej. restablecer su contraseña) sería
    quedarse con más permisos de los propios.

    Raises:
        PermissionEscalationError: ``target`` es admin de instancia y ``actor`` no, o el rol de ``target`` tiene algún
            permiso que ``actor`` no tiene.
    """
    if actor.is_instance_admin or actor.id == target.id:
        return
    if target.is_instance_admin:
        raise PermissionEscalationError("Solo un administrador de la instancia gestiona a otro.")
    tenant_roles.check_grant(actor, list(target.role.permissions or []))


def _resolve_role(db: Session, tenant_id: int, role_id: int | None, actor: User | None) -> TenantRole:
    """Rol ``role_id`` del tenant (o «Usuario» si es ``None``) que ``actor`` puede asignar."""
    role = (
        tenant_roles.builtin_role(db, tenant_id, "user")
        if role_id is None
        else tenant_roles.get_role(db, role_id, tenant_id=tenant_id)
    )
    if actor is not None:
        tenant_roles.check_grant(actor, list(role.permissions or []))
    return role


def create_user(
    db: Session,
    *,
    username: str,
    display_name: str,
    password: str,
    settings: Settings,
    ctx: RequestContext,
    actor: User | None,
    tenant_id: int = DEFAULT_TENANT_ID,
    role_id: int | None = None,
    is_instance_admin: bool = False,
) -> User:
    """Crea un usuario activo del tenant y lo audita. ``actor`` es ``None`` en el CLI (primer admin).

    Raises:
        UsernameTakenError: El nombre ya existe (en toda la instancia).
        PasswordPolicyError: La contraseña no cumple la política.
        RoleNotFoundError: El rol no es del tenant.
        PermissionEscalationError: ``actor`` da un rol con permisos que no tiene, o la condición de admin de instancia
            sin serlo.
    """
    if actor is not None and is_instance_admin and not actor.is_instance_admin:
        raise PermissionEscalationError("Solo un administrador de la instancia crea otro.")
    get_tenant(db, tenant_id)
    username = normalize_username(username)
    check_policy(password, username=username, min_length=settings.password_min_length)
    if get_by_username(db, username) is not None:
        raise UsernameTakenError()
    role = _resolve_role(db, tenant_id, role_id, actor)
    user = User(
        tenant_id=tenant_id,
        username=username,
        display_name=display_name.strip() or username,
        password_hash=hash_password(password),
        role_id=role.id,
        is_instance_admin=is_instance_admin,
        is_active=True,
        failed_attempts=0,
    )
    db.add(user)
    db.flush()
    audit.record(
        db,
        action=AuditAction.USER_CREATE,
        ctx=ctx,
        actor_id=actor.id if actor else None,
        target_type="user",
        target_id=user.id,
        details={"username": user.username, "role": role.name, "instance_admin": is_instance_admin},
        tenant_id=tenant_id,
    )
    db.commit()
    return user


def _move(db: Session, user: User, tenant_id: int, role: TenantRole, *, actor: User, ctx: RequestContext) -> None:
    """Pasa ``user`` a otro tenant: pierde sus membresías de proyecto y sus sesiones."""
    old = user.tenant_id
    result = db.execute(delete(ProjectMember).where(ProjectMember.user_id == user.id))
    removed = int(getattr(result, "rowcount", 0) or 0)
    user.tenant_id = tenant_id
    user.role_id = role.id
    revoke_user_sessions(db, user.id)
    audit.record(
        db,
        action=AuditAction.USER_MOVE,
        ctx=ctx,
        actor_id=actor.id,
        target_type="user",
        target_id=user.id,
        details={"from_tenant": old, "to_tenant": tenant_id, "memberships_removed": removed},
    )


def update_user(
    db: Session, user: User, changes: UserChanges, *, actor: User, settings: Settings, ctx: RequestContext
) -> User:
    """Aplica ``changes`` a ``user``.

    Desactivar, restablecer la contraseña, cambiar de rol o de tenant revoca las sesiones del usuario; reactivar,
    restablecer la contraseña o ``unlock`` quitan el bloqueo por intentos.

    Raises:
        SelfModificationError: Se intenta desactivar, cambiar de rol o de tenant, o quitarse ser admin de instancia a
            sí mismo.
        LastAdminError: Quedaría la instancia sin administradores activos.
        LastTenantManagerError: El tenant se quedaría sin quien gestione sus usuarios.
        PermissionEscalationError: ``user`` tiene permisos que ``actor`` no tiene (o es admin de instancia), se da un
            rol con permisos que ``actor`` no tiene, o algo que solo hace el admin de instancia (marcar admins de
            instancia, mover de tenant).
        PasswordPolicyError: La contraseña nueva no cumple la política.
    """
    check_can_manage(actor, user)
    moving = changes.tenant_id is not None and changes.tenant_id != user.tenant_id
    new_tenant = changes.tenant_id if moving and changes.tenant_id is not None else user.tenant_id
    instance_change = changes.is_instance_admin is not None and changes.is_instance_admin != user.is_instance_admin
    if (moving or instance_change) and not actor.is_instance_admin:
        raise PermissionEscalationError("Solo un administrador de la instancia puede hacerlo.")
    new_role: TenantRole | None = None
    if moving or (changes.role_id is not None and changes.role_id != user.role_id):
        new_role = _resolve_role(db, new_tenant, changes.role_id, actor)
    deactivating = changes.is_active is False and user.is_active
    if user.id == actor.id and (deactivating or new_role is not None or moving or changes.is_instance_admin is False):
        raise SelfModificationError()

    loses_instance_admin = (
        user.is_instance_admin and user.is_active and (deactivating or changes.is_instance_admin is False)
    )
    if loses_instance_admin and _active_instance_admins(db) <= 1:
        raise LastAdminError()
    loses_manager = (
        user.is_active
        and USERS_MANAGE in (user.role.permissions or [])
        and (deactivating or moving or (new_role is not None and USERS_MANAGE not in (new_role.permissions or [])))
    )
    if loses_manager and not actor.is_instance_admin and _managers(db, user.tenant_id, excluding=user.id) == 0:
        raise LastTenantManagerError()

    changed: list[str] = []
    if changes.display_name is not None and changes.display_name.strip() != user.display_name:
        user.display_name = changes.display_name.strip() or user.username
        changed.append("display_name")
    if moving and new_role is not None:
        _move(db, user, new_tenant, new_role, actor=actor, ctx=ctx)
    elif new_role is not None:
        user.role_id = new_role.id
        revoke_user_sessions(db, user.id)
        changed.append("role")
    if instance_change and changes.is_instance_admin is not None:
        user.is_instance_admin = changes.is_instance_admin
        revoke_user_sessions(db, user.id)
        changed.append("is_instance_admin")
    if changes.password is not None:
        check_policy(changes.password, username=user.username, min_length=settings.password_min_length)
        user.password_hash = hash_password(changes.password)
        user.password_changed_at = utcnow()
        user.failed_attempts = 0
        user.locked_until = None
        revoke_user_sessions(db, user.id)
        audit.record(
            db,
            action=AuditAction.USER_PASSWORD_RESET,
            ctx=ctx,
            actor_id=actor.id,
            target_type="user",
            target_id=user.id,
        )
    if changes.unlock and (user.locked_until is not None or user.failed_attempts):
        user.failed_attempts = 0
        user.locked_until = None
        audit.record(
            db, action=AuditAction.USER_UNLOCK, ctx=ctx, actor_id=actor.id, target_type="user", target_id=user.id
        )
    if changes.is_active is not None and changes.is_active != user.is_active:
        user.is_active = changes.is_active
        if changes.is_active:
            user.failed_attempts = 0
            user.locked_until = None
        else:
            revoke_user_sessions(db, user.id)
        audit.record(
            db,
            action=AuditAction.USER_REACTIVATE if changes.is_active else AuditAction.USER_DEACTIVATE,
            ctx=ctx,
            actor_id=actor.id,
            target_type="user",
            target_id=user.id,
        )
    if changed:
        details: dict[str, object] = {"fields": changed}
        if "role" in changed and new_role is not None:
            details["role"] = new_role.name
        if "is_instance_admin" in changed:
            details["instance_admin"] = user.is_instance_admin
        audit.record(
            db,
            action=AuditAction.USER_UPDATE,
            ctx=ctx,
            actor_id=actor.id,
            target_type="user",
            target_id=user.id,
            details=details,
        )
    db.commit()
    db.refresh(user)
    return user
