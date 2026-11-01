"""Modelos SQLAlchemy de ``config.db``.

Fase 1: identidad (``tenants``, ``users``, ``sessions``, ``audit_log``). Fase 2: ``locations`` y ``app_settings``.
Fase 3: ``projects``, ``project_members``, ``runs``, ``run_events``, ``artifacts``, ``workers`` y ``periodic_tasks``.
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
    text,
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


ProjectStatus = Literal["active", "deleted"]
MemberRole = Literal["owner", "editor", "viewer"]
MEMBER_ROLES: tuple[MemberRole, ...] = ("owner", "editor", "viewer")


class Project(Base):
    """Proyecto: lee de una ubicación origen y escribe sus salidas en una carpeta propia de una ubicación destino.

    Las rutas se guardan **relativas** a su ubicación (``source_subpaths``, ``destination_subpath``) y se vuelven a
    resolver en cada uso. El estado de doc_organize vive en ``DOW_DATA_DIR/projects/<id>`` (ADR-005). Borrar un proyecto
    es lógico (``status = deleted``): sus runs y la auditoría siguen apuntando a él.
    """

    __tablename__ = "projects"
    __table_args__ = (CheckConstraint("status IN ('active', 'deleted')", name="status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True, default=DEFAULT_TENANT_ID)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(String(1024), default=None)
    source_location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"), index=True)
    source_subpaths: Mapped[list[str]] = mapped_column(JSON)
    destination_location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"), index=True)
    destination_subpath: Mapped[str] = mapped_column(String(4096))
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), default=None)

    source_location: Mapped[Location] = relationship(foreign_keys=[source_location_id], lazy="joined")
    destination_location: Mapped[Location] = relationship(foreign_keys=[destination_location_id], lazy="joined")
    members: Mapped[list[ProjectMember]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )


class ProjectMember(Base):
    """Usuario con acceso a un proyecto: ``owner`` lo gestiona, ``editor`` lanza runs y ``viewer`` solo consulta."""

    __tablename__ = "project_members"
    __table_args__ = (CheckConstraint("role IN ('owner', 'editor', 'viewer')", name="role"),)

    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True)
    role: Mapped[str] = mapped_column(String(16))
    added_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)
    added_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    project: Mapped[Project] = relationship(back_populates="members")
    user: Mapped[User] = relationship(foreign_keys=[user_id], lazy="joined")


RunStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]
RunQueue = Literal["cpu", "gpu"]
ACTIVE_RUN_STATUSES: tuple[RunStatus, ...] = ("queued", "running")
FINISHED_RUN_STATUSES: tuple[RunStatus, ...] = ("succeeded", "failed", "cancelled")


class Run(Base):
    """Ejecución encolada (ADR-002): la API la crea, un worker la reclama y su subproceso la ejecuta.

    ``params`` y ``result`` nunca contienen secretos ni rutas del contenedor. El índice único parcial
    ``uq_runs_project_write`` garantiza en la BD una sola operación de escritura activa por proyecto.
    """

    __tablename__ = "runs"
    __table_args__ = (
        CheckConstraint("status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')", name="status"),
        CheckConstraint("queue IN ('cpu', 'gpu')", name="queue"),
        Index("ix_runs_claim", "status", "queue", "created_at"),
        Index("ix_runs_project_created", "project_id", "created_at"),
        Index(
            "uq_runs_project_write",
            "project_id",
            unique=True,
            sqlite_where=text("is_write AND status IN ('queued', 'running')"),
            postgresql_where=text("is_write AND status IN ('queued', 'running')"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), default=None)
    operation: Mapped[str] = mapped_column(String(32))
    queue: Mapped[str] = mapped_column(String(8), default="cpu")
    status: Mapped[str] = mapped_column(String(16), default="queued")
    is_write: Mapped[bool] = mapped_column(default=False)
    params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    progress: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    error_code: Mapped[str | None] = mapped_column(String(64), default=None)
    error_message: Mapped[str | None] = mapped_column(String(1024), default=None)
    cancel_requested: Mapped[bool] = mapped_column(default=False)
    #: Fase crítica (borrar, mover): el worker no termina el subproceso por una cancelación, solo por el timeout.
    uninterruptible: Mapped[bool] = mapped_column(default=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)
    worker_id: Mapped[str | None] = mapped_column(String(128), default=None)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), default=None)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), default=None)
    heartbeat_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), default=None)
    workspace_purged_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), default=None)

    creator: Mapped[User | None] = relationship(lazy="joined")
    artifacts: Mapped[list[Artifact]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True, order_by="Artifact.id"
    )

    @property
    def created_by_username(self) -> str | None:
        """Usuario que lanzó el run, si lo hay."""
        return self.creator.username if self.creator else None


class RunEvent(Base):
    """Evento de un run, fuente del SSE: ``seq`` es el ``id`` del evento y permite reanudar con ``Last-Event-ID``."""

    __tablename__ = "run_events"

    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), primary_key=True)
    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    ts: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    type: Mapped[str] = mapped_column(String(16))
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


ArtifactKind = Literal["log", "output", "report"]


class Artifact(Base):
    """Fichero que deja un run en su carpeta del workspace; se descarga solo por id (ADR-005)."""

    __tablename__ = "artifacts"
    __table_args__ = (CheckConstraint("kind IN ('log', 'output', 'report')", name="kind"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(16))
    rel_path: Mapped[str] = mapped_column(String(1024))
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    content_type: Mapped[str] = mapped_column(String(128))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    run: Mapped[Run] = relationship(back_populates="artifacts")


class Worker(Base):
    """Proceso worker vivo o reciente: colas que atiende, latido y capacidades de su contenedor (pendiente de F2)."""

    __tablename__ = "workers"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    queues: Mapped[list[str]] = mapped_column(JSON)
    version: Mapped[str] = mapped_column(String(32))
    doc_organize_version: Mapped[str | None] = mapped_column(String(32), default=None)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    heartbeat_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    capabilities: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    capabilities_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), default=None)
    refresh_requested: Mapped[bool] = mapped_column(default=False)


class PeriodicTask(Base):
    """Marca de la última ejecución de una tarea periódica del worker; con varios workers solo uno la reclama."""

    __tablename__ = "periodic_tasks"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    last_run_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), default=None)
    claimed_by: Mapped[str | None] = mapped_column(String(128), default=None)
