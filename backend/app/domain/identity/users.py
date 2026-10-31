"""Administración de usuarios: alta, edición, desactivación y reactivación (sin borrado físico)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Role, User, utcnow
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


def normalize_username(username: str) -> str:
    """Los nombres de usuario no distinguen mayúsculas."""
    return username.strip().lower()


@dataclass(frozen=True)
class UserChanges:
    """Cambios de un ``PATCH``; ``None`` significa «sin cambio»."""

    display_name: str | None = None
    role: Role | None = None
    is_active: bool | None = None
    password: str | None = None
    unlock: bool = False


def get_user(db: Session, user_id: int) -> User:
    """Usuario por id.

    Raises:
        UserNotFoundError: No existe.
    """
    user = db.get(User, user_id)
    if user is None:
        raise UserNotFoundError()
    return user


def get_by_username(db: Session, username: str) -> User | None:
    """Usuario por nombre (normalizado) o ``None``."""
    return db.scalar(select(User).where(User.username == normalize_username(username)))


def list_users(db: Session, *, q: str | None, limit: int, offset: int) -> tuple[list[User], int]:
    """Usuarios ordenados por nombre, filtrados por texto en usuario o nombre visible."""
    query = select(User)
    if q:
        pattern = f"%{q.strip().lower()}%"
        query = query.where(or_(User.username.like(pattern), func.lower(User.display_name).like(pattern)))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(User.username).limit(limit).offset(offset)).all()
    return list(rows), total


def _active_admins(db: Session) -> int:
    return db.scalar(select(func.count()).where(User.role == "admin", User.is_active.is_(True))) or 0


def create_user(
    db: Session,
    *,
    username: str,
    display_name: str,
    password: str,
    role: Role,
    settings: Settings,
    ctx: RequestContext,
    actor_id: int | None,
) -> User:
    """Crea un usuario activo y lo audita.

    Raises:
        UsernameTakenError: El nombre ya existe.
        PasswordPolicyError: La contraseña no cumple la política.
    """
    username = normalize_username(username)
    check_policy(password, username=username, min_length=settings.password_min_length)
    if get_by_username(db, username) is not None:
        raise UsernameTakenError()
    user = User(
        username=username,
        display_name=display_name.strip() or username,
        password_hash=hash_password(password),
        role=role,
        is_active=True,
        failed_attempts=0,
    )
    db.add(user)
    db.flush()
    audit.record(
        db,
        action=AuditAction.USER_CREATE,
        ctx=ctx,
        actor_id=actor_id,
        target_type="user",
        target_id=user.id,
        details={"username": user.username, "role": role},
    )
    db.commit()
    return user


def update_user(
    db: Session, user: User, changes: UserChanges, *, actor: User, settings: Settings, ctx: RequestContext
) -> User:
    """Aplica ``changes`` a ``user``.

    Desactivar o restablecer la contraseña revoca las sesiones del usuario; reactivar, restablecer la contraseña o
    ``unlock`` quitan el bloqueo por intentos.

    Raises:
        SelfModificationError: El admin intenta desactivarse o quitarse el rol.
        LastAdminError: Quedaría el sistema sin administradores activos.
        PasswordPolicyError: La contraseña nueva no cumple la política.
    """
    loses_admin = user.role == "admin" and user.is_active and (changes.role == "user" or changes.is_active is False)
    if loses_admin and user.id == actor.id:
        raise SelfModificationError()
    if loses_admin and _active_admins(db) <= 1:
        raise LastAdminError()

    changed: list[str] = []
    if changes.display_name is not None and changes.display_name.strip() != user.display_name:
        user.display_name = changes.display_name.strip() or user.username
        changed.append("display_name")
    if changes.role is not None and changes.role != user.role:
        user.role = changes.role
        changed.append("role")
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
        audit.record(
            db,
            action=AuditAction.USER_UPDATE,
            ctx=ctx,
            actor_id=actor.id,
            target_type="user",
            target_id=user.id,
            details={"fields": changed, **({"role": user.role} if "role" in changed else {})},
        )
    db.commit()
    return user
