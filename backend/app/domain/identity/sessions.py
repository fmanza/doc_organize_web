"""Sesiones de servidor: emisión, validación con caducidad por inactividad y absoluta, y revocación."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.core.config import Settings
from app.core.security import hash_token, new_session_token
from app.db.models import User, UserSession, utcnow
from app.domain.identity.audit import RequestContext
from app.domain.identity.errors import SessionNotFoundError

# ``last_seen_at`` se escribe como mucho una vez por minuto y sesión: SQLite tiene un único escritor.
TOUCH_INTERVAL = timedelta(seconds=60)


@dataclass(frozen=True)
class IssuedSession:
    """Sesión recién creada con su token en claro (solo para la cookie; no se persiste)."""

    token: str
    session: UserSession


def _idle(settings: Settings) -> timedelta:
    return timedelta(minutes=settings.session_idle_minutes)


def create_session(
    db: Session, user: User, ctx: RequestContext, settings: Settings, *, now: datetime | None = None
) -> IssuedSession:
    """Crea una sesión para ``user`` (sin confirmar la transacción)."""
    now = now or utcnow()
    token = new_session_token()
    session = UserSession(
        token_hash=hash_token(token),
        user_id=user.id,
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(hours=settings.session_absolute_hours),
        ip=ctx.ip,
        user_agent=ctx.user_agent,
    )
    db.add(session)
    db.flush()
    return IssuedSession(token=token, session=session)


def is_expired(session: UserSession, settings: Settings, now: datetime) -> bool:
    """Caducada por tiempo absoluto o por inactividad."""
    return now >= session.expires_at or now >= session.last_seen_at + _idle(settings)


def resolve_session(db: Session, token: str, settings: Settings, *, now: datetime | None = None) -> UserSession | None:
    """Sesión válida para ``token`` o ``None``.

    Borra la sesión si ha caducado o su usuario está desactivado, y actualiza ``last_seen_at`` como mucho una vez por
    ``TOUCH_INTERVAL``.
    """
    now = now or utcnow()
    session = db.scalar(
        select(UserSession).options(joinedload(UserSession.user)).where(UserSession.token_hash == hash_token(token))
    )
    if session is None:
        return None
    if is_expired(session, settings, now) or not session.user.is_active:
        db.delete(session)
        db.commit()
        return None
    if now - session.last_seen_at >= TOUCH_INTERVAL:
        session.last_seen_at = now
        db.commit()
    return session


def find_by_token(db: Session, token: str) -> UserSession | None:
    """Sesión por token, sin validar caducidad."""
    return db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(token)))


def purge_expired(db: Session, settings: Settings, *, now: datetime | None = None) -> int:
    """Borra las sesiones caducadas de todos los usuarios (sin confirmar)."""
    now = now or utcnow()
    result = db.execute(
        delete(UserSession).where(or_(UserSession.expires_at <= now, UserSession.last_seen_at <= now - _idle(settings)))
    )
    return int(getattr(result, "rowcount", 0) or 0)


def revoke_user_sessions(db: Session, user_id: int, *, except_id: int | None = None) -> int:
    """Borra las sesiones de un usuario, salvo ``except_id`` (sin confirmar)."""
    query = delete(UserSession).where(UserSession.user_id == user_id)
    if except_id is not None:
        query = query.where(UserSession.id != except_id)
    result = db.execute(query)
    return int(getattr(result, "rowcount", 0) or 0)


def get_session_by_id(db: Session, session_id: int) -> UserSession:
    """Sesión por id.

    Raises:
        SessionNotFoundError: No existe.
    """
    session = db.get(UserSession, session_id)
    if session is None:
        raise SessionNotFoundError()
    return session


def list_sessions(
    db: Session, settings: Settings, *, user_id: int | None, limit: int, offset: int, now: datetime | None = None
) -> tuple[list[UserSession], int]:
    """Sesiones vigentes, más recientes primero, opcionalmente de un usuario."""
    now = now or utcnow()
    query = select(UserSession).where(UserSession.expires_at > now, UserSession.last_seen_at > now - _idle(settings))
    if user_id is not None:
        query = query.where(UserSession.user_id == user_id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(
        query.options(joinedload(UserSession.user))
        .order_by(UserSession.last_seen_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return list(rows), total
