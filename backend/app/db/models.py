"""Modelos SQLAlchemy de ``config.db``.

Fase 1: identidad (``tenants``, ``users``, ``sessions``, ``audit_log``). Fase 2: ``locations`` y ``app_settings``.
Solo tipos portables (D8): las fechas se guardan en UTC con ``UTCDateTime``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Final, Literal

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

Role = Literal["admin", "user"]
ROLES: tuple[Role, ...] = ("admin", "user")

#: Tenant único hasta la Fase 9 (ADR-003, ADR-013): lo crea la migración ``0002``.
DEFAULT_TENANT_ID: Final = 1
DEFAULT_TENANT_SLUG: Final = "default"


def utcnow() -> datetime:
    """Instante actual en UTC con zona."""
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator[datetime]):
    """Fecha en UTC: SQLite la guarda sin zona y se devuelve siempre con ``tzinfo=UTC``."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Se esperaba una fecha con zona horaria")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        return None if value is None else value.replace(tzinfo=UTC)


class Tenant(Base):
    """Organización aislada (Fase 9). Hasta entonces solo existe ``default``."""

    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class User(Base):
    """Usuario de la aplicación. No se borra: se desactiva (la auditoría lo referencia).

    ``username`` es único en toda la instancia (no por tenant) hasta la Fase 9.
    """

    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('admin', 'user')", name="role"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True, default=DEFAULT_TENANT_ID)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(String(128))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16))
    is_active: Mapped[bool] = mapped_column(default=True)
    failed_attempts: Mapped[int] = mapped_column(default=0)
    locked_until: Mapped[datetime | None] = mapped_column(UTCDateTime(), default=None)
    password_changed_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)

    sessions: Mapped[list[UserSession]] = relationship(back_populates="user", passive_deletes=True)


class UserSession(Base):
    """Sesión de servidor. Solo se guarda el SHA-256 del token; el token viaja en la cookie de sesión."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    ip: Mapped[str | None] = mapped_column(String(64), default=None)
    user_agent: Mapped[str | None] = mapped_column(String(255), default=None)

    user: Mapped[User] = relationship(back_populates="sessions")


class AuditEntry(Base):
    """Evento de auditoría. ``details`` nunca contiene secretos."""

    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_log_ts", "ts"), Index("ix_audit_log_action", "action"))

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True, default=DEFAULT_TENANT_ID)
    ts: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)
    action: Mapped[str] = mapped_column(String(64))
    outcome: Mapped[str] = mapped_column(String(16), default="success")
    target_type: Mapped[str | None] = mapped_column(String(32), default=None)
    target_id: Mapped[str | None] = mapped_column(String(64), default=None)
    ip: Mapped[str | None] = mapped_column(String(64), default=None)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)

    actor: Mapped[User | None] = relationship(lazy="joined")

    @property
    def actor_username(self) -> str | None:
        """Usuario que hizo la acción, si lo hay."""
        return self.actor.username if self.actor else None


LocationKind = Literal["local", "network"]
LocationUsage = Literal["source", "destination", "both"]
LocationAccess = Literal["ro", "rw"]
LocationStatus = Literal["unknown", "ok", "degraded", "unavailable"]


class Location(Base):
    """Carpeta raíz registrada por un admin bajo ``DOW_LOCATIONS_ROOT`` (ADR-007).

    ``container_path`` es la ruta resuelta dentro del contenedor y no cambia tras crearla; ``display_path`` es solo
    texto para el usuario y nunca se usa para acceder. El estado lo escribe el último sondeo.
    """

    __tablename__ = "locations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_locations_tenant_name"),
        CheckConstraint("kind IN ('local', 'network')", name="kind"),
        CheckConstraint("usage IN ('source', 'destination', 'both')", name="usage"),
        CheckConstraint("access IN ('ro', 'rw')", name="access"),
        CheckConstraint("status IN ('unknown', 'ok', 'degraded', 'unavailable')", name="status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True, default=DEFAULT_TENANT_ID)
    name: Mapped[str] = mapped_column(String(128))
    container_path: Mapped[str] = mapped_column(String(1024), unique=True)
    display_path: Mapped[str | None] = mapped_column(String(1024), default=None)
    kind: Mapped[str] = mapped_column(String(16))
    usage: Mapped[str] = mapped_column(String(16))
    access: Mapped[str] = mapped_column(String(8))
    visibility: Mapped[str] = mapped_column(String(16), default="global")
    status: Mapped[str] = mapped_column(String(16), default="unknown")
    status_reasons: Mapped[list[str] | None] = mapped_column(JSON, default=None)
    latency_ms: Mapped[float | None] = mapped_column(Float, default=None)
    free_bytes: Mapped[int | None] = mapped_column(BigInteger, default=None)
    writable: Mapped[bool | None] = mapped_column(default=None)
    probed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), default=None)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


class AppSetting(Base):
    """Ajuste que un admin cambia desde la web (ADR-012); sin fila, vale la variable ``DOW_*``.

    Solo admite las claves de ``app/domain/settings/service.py`` (no es un almacén genérico ni guarda secretos).
    """

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)
