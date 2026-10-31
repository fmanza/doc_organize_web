"""Casos de uso de autenticación: inicio y cierre de sesión, cambio de contraseña y revocación."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import User, UserSession, utcnow
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction, RequestContext
from app.domain.identity.errors import InvalidCredentialsError, SessionNotFoundError, WrongCurrentPasswordError
from app.domain.identity.passwords import burn_verification, check_policy, hash_password, verify_password
from app.domain.identity.sessions import (
    IssuedSession,
    create_session,
    find_by_token,
    get_session_by_id,
    purge_expired,
    revoke_user_sessions,
)
from app.domain.identity.users import get_by_username

logger = logging.getLogger(__name__)


def login(
    db: Session,
    *,
    username: str,
    password: str,
    settings: Settings,
    ctx: RequestContext,
    previous_token: str | None = None,
    now: datetime | None = None,
) -> IssuedSession:
    """Autentica y emite una sesión nueva (rotación: la sesión previa del navegador se borra).

    Tras ``login_max_attempts`` fallos seguidos la cuenta queda bloqueada ``login_lockout_minutes``.

    Raises:
        InvalidCredentialsError: Mismo error para usuario inexistente, desactivado, bloqueado o contraseña errónea.
    """
    now = now or utcnow()
    user = get_by_username(db, username)

    def fail(reason: str, target: User | None) -> InvalidCredentialsError:
        audit.record(
            db,
            action=AuditAction.LOGIN,
            ctx=ctx,
            actor_id=None,
            outcome="failure",
            target_type="user" if target else None,
            target_id=target.id if target else None,
            # El nombre probado solo se guarda si existe: un usuario inexistente puede ser una contraseña mal tecleada.
            details={"username": target.username, "reason": reason} if target else {"reason": reason},
        )
        db.commit()
        logger.info(
            "Inicio de sesión rechazado",
            extra={"user_id": target.id if target else None, "reason": reason, "ip": ctx.ip},
        )
        return InvalidCredentialsError()

    if user is None or not user.is_active:
        burn_verification(password)
        raise fail("unknown_user" if user is None else "inactive", user)
    if user.locked_until is not None and user.locked_until > now:
        burn_verification(password)
        raise fail("locked", user)

    valid, new_hash = verify_password(password, user.password_hash)
    if not valid:
        user.failed_attempts += 1
        if user.failed_attempts >= settings.login_max_attempts:
            user.failed_attempts = 0
            user.locked_until = now + timedelta(minutes=settings.login_lockout_minutes)
            audit.record(
                db,
                action=AuditAction.LOCKOUT,
                ctx=ctx,
                actor_id=None,
                outcome="failure",
                target_type="user",
                target_id=user.id,
                details={"minutes": settings.login_lockout_minutes},
            )
        raise fail("bad_password", user)

    user.failed_attempts = 0
    user.locked_until = None
    if new_hash is not None:
        user.password_hash = new_hash
    if previous_token:
        previous = find_by_token(db, previous_token)
        if previous is not None:
            db.delete(previous)
    purge_expired(db, settings, now=now)
    issued = create_session(db, user, ctx, settings, now=now)
    audit.record(db, action=AuditAction.LOGIN, ctx=ctx, actor_id=user.id, target_type="user", target_id=user.id)
    db.commit()
    logger.info("Inicio de sesión", extra={"user_id": user.id, "session_id": issued.session.id, "ip": ctx.ip})
    return issued


def logout(db: Session, session: UserSession, *, ctx: RequestContext) -> None:
    """Cierra la sesión actual."""
    audit.record(
        db, action=AuditAction.LOGOUT, ctx=ctx, actor_id=session.user_id, target_type="session", target_id=session.id
    )
    db.delete(session)
    db.commit()


def change_password(
    db: Session,
    session: UserSession,
    *,
    current_password: str,
    new_password: str,
    settings: Settings,
    ctx: RequestContext,
) -> None:
    """Cambia la contraseña del usuario de ``session`` y revoca sus demás sesiones.

    Raises:
        WrongCurrentPasswordError: La contraseña actual no coincide.
        PasswordPolicyError: La nueva no cumple la política.
    """
    user = session.user
    valid, _ = verify_password(current_password, user.password_hash)
    if not valid:
        audit.record(
            db,
            action=AuditAction.PASSWORD_CHANGE,
            ctx=ctx,
            actor_id=user.id,
            outcome="failure",
            target_type="user",
            target_id=user.id,
        )
        db.commit()
        raise WrongCurrentPasswordError()
    check_policy(new_password, username=user.username, min_length=settings.password_min_length)
    user.password_hash = hash_password(new_password)
    user.password_changed_at = utcnow()
    revoked = revoke_user_sessions(db, user.id, except_id=session.id)
    audit.record(
        db,
        action=AuditAction.PASSWORD_CHANGE,
        ctx=ctx,
        actor_id=user.id,
        target_type="user",
        target_id=user.id,
        details={"revoked_sessions": revoked},
    )
    db.commit()


def revoke_session(db: Session, session_id: int, *, actor: User, ctx: RequestContext) -> None:
    """Cierra una sesión: el admin, cualquiera; un usuario, solo las suyas.

    Raises:
        SessionNotFoundError: No existe, o es de otro usuario y ``actor`` no es admin (no se revela que exista).
    """
    session = get_session_by_id(db, session_id)
    if actor.role != "admin" and session.user_id != actor.id:
        raise SessionNotFoundError()
    audit.record(
        db,
        action=AuditAction.SESSION_REVOKE,
        ctx=ctx,
        actor_id=actor.id,
        target_type="session",
        target_id=session.id,
        details={"user_id": session.user_id},
    )
    db.delete(session)
    db.commit()
