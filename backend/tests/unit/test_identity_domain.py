"""Reglas de dominio de identidad sobre una ``config.db`` temporal (sin HTTP)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import AuditEntry, User, UserSession, utcnow
from app.domain.identity import auth
from app.domain.identity.audit import RequestContext
from app.domain.identity.errors import InvalidCredentialsError, LastAdminError, SelfModificationError
from app.domain.identity.sessions import create_session, is_expired, resolve_session
from app.domain.identity.users import UserChanges, update_user
from tests.conftest import ADMIN_PASSWORD, USER_PASSWORD

CTX = RequestContext(ip="10.0.0.1", user_agent="pytest")


def test_lockout_after_max_attempts_and_unlock_after_timeout(db: Session, migrated: Settings, user: User) -> None:
    now = utcnow()
    for _ in range(migrated.login_max_attempts):
        with pytest.raises(InvalidCredentialsError):
            auth.login(db, username="ana", password="mala-contrasena", settings=migrated, ctx=CTX, now=now)
    db.refresh(user)
    assert user.locked_until is not None

    # Bloqueada: ni la contraseña correcta entra.
    with pytest.raises(InvalidCredentialsError):
        auth.login(db, username="ana", password=USER_PASSWORD, settings=migrated, ctx=CTX, now=now)

    later = now + timedelta(minutes=migrated.login_lockout_minutes, seconds=1)
    issued = auth.login(db, username="ANA", password=USER_PASSWORD, settings=migrated, ctx=CTX, now=later)
    assert issued.session.user_id == user.id
    actions = db.scalars(select(AuditEntry.action).where(AuditEntry.action == "auth.lockout")).all()
    assert actions == ["auth.lockout"]


def test_session_expires_by_idle_and_absolute_time(db: Session, migrated: Settings, user: User) -> None:
    now = utcnow()
    issued = create_session(db, user, CTX, migrated, now=now)
    session = issued.session

    assert not is_expired(session, migrated, now + timedelta(minutes=migrated.session_idle_minutes - 1))
    assert is_expired(session, migrated, now + timedelta(minutes=migrated.session_idle_minutes))
    session.last_seen_at = now + timedelta(hours=migrated.session_absolute_hours)
    assert is_expired(session, migrated, now + timedelta(hours=migrated.session_absolute_hours))


def test_resolve_deletes_expired_session(db: Session, migrated: Settings, user: User) -> None:
    now = utcnow()
    issued = create_session(db, user, CTX, migrated, now=now)
    db.commit()

    later = now + timedelta(minutes=migrated.session_idle_minutes + 1)
    assert resolve_session(db, issued.token, migrated, now=later) is None
    assert db.scalar(select(UserSession).where(UserSession.id == issued.session.id)) is None


def test_last_admin_cannot_be_demoted_or_deactivated(
    db: Session, migrated: Settings, admin: User, make_user: Callable[..., User]
) -> None:
    other = make_user("otro", ADMIN_PASSWORD, "admin")

    with pytest.raises(SelfModificationError):
        update_user(db, admin, UserChanges(role="user"), actor=admin, settings=migrated, ctx=CTX)

    update_user(db, other, UserChanges(is_active=False), actor=admin, settings=migrated, ctx=CTX)
    # ``admin`` es ahora el único activo; otro admin (reactivado) no puede dejarlo sin rol.
    with pytest.raises(LastAdminError):
        update_user(db, admin, UserChanges(role="user"), actor=other, settings=migrated, ctx=CTX)
