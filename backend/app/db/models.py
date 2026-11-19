"""Modelos SQLAlchemy de ``config.db``.

Fase 1: identidad (``tenants``, ``users``, ``sessions``, ``audit_log``). Fase 2: ``locations`` y ``app_settings``.
Fase 3: ``projects``, ``project_members``, ``runs``, ``run_events``, ``artifacts``, ``workers`` y ``periodic_tasks``.
Fase 4: ``scanned_folders`` y ``scan_errors``. Fase 6: ``duplicate_groups``. Fase 7: ``taxonomy_templates``,
``project_contexts`` y ``context_documents``.
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
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
    false,
    text,
    true,
)
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

#: Tenant inicial (ADR-003, ADR-013): lo crea la migración ``0002``. Desde la Fase 9 puede haber más.
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
    """Organización aislada (Fase 9, ADR-013): sus usuarios, proyectos, ubicaciones, plantillas, roles y auditoría."""

    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


class TenantRole(Base):
    """Rol de un tenant con permisos de administración (Fase 9). ``builtin`` marca los roles base (``admin``,
    ``user``), que no se borran ni cambian de permisos. ``permissions`` lleva claves de
    ``app/domain/tenancy/permissions.py``."""

    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_roles_tenant_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    name: Mapped[str] = mapped_column(String(64))
    builtin: Mapped[str | None] = mapped_column(String(16), default=None)
    permissions: Mapped[list[str]] = mapped_column(JSON, default=list)
    #: Sin FK: ``users.role_id`` ya apunta aquí y un ciclo de claves complicaría la migración.
    created_by: Mapped[int | None] = mapped_column(Integer, default=None)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


class User(Base):
    """Usuario de la aplicación. No se borra: se desactiva (la auditoría lo referencia).

    ``username`` es único en toda la instancia (decisión de la Fase 9). Pertenece a un tenant y tiene un rol de ese
    tenant. ``is_instance_admin`` da lo que es del servidor y deja actuar en cualquier tenant (``acting_tenant_id``).
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True, default=DEFAULT_TENANT_ID)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(String(128))
    password_hash: Mapped[str] = mapped_column(String(255))
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), index=True)
    is_instance_admin: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    failed_attempts: Mapped[int] = mapped_column(default=0)
    locked_until: Mapped[datetime | None] = mapped_column(UTCDateTime(), default=None)
    password_changed_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)

    sessions: Mapped[list[UserSession]] = relationship(back_populates="user", passive_deletes=True)
    role: Mapped[TenantRole] = relationship(lazy="joined")
    tenant: Mapped[Tenant] = relationship(lazy="joined")

    def act_in(self, tenant_id: int | None) -> None:
        """Fija el tenant en el que actúa en esta petición (lo hace la dependencia de sesión; no se guarda en la BD)."""
        self.__dict__["_acting_tenant_id"] = tenant_id

    @property
    def acting_tenant_id(self) -> int | None:
        """Tenant elegido con el selector en esta petición, o ``None``."""
        value = self.__dict__.get("_acting_tenant_id")
        return value if isinstance(value, int) else None

    @property
    def scope_tenant_id(self) -> int:
        """Tenant de las consultas de esta petición (ADR-013)."""
        if self.is_instance_admin and self.acting_tenant_id is not None:
            return self.acting_tenant_id
        return self.tenant_id

    @property
    def permissions(self) -> list[str]:
        """Permisos en el tenant activo: todos para un admin de instancia; si no, los de su rol."""
        from app.domain.tenancy.permissions import PERMISSIONS, normalize

        granted = PERMISSIONS if self.is_instance_admin else normalize(self.role.permissions or [])
        return [str(p) for p in granted]

    def can(self, permission: str) -> bool:
        """Si tiene ``permission`` en el tenant activo."""
        return permission in self.permissions


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
    #: Tenant elegido con el selector (solo admins de instancia; ``None`` = el suyo).
    acting_tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenants.id", ondelete="SET NULL"), default=None)

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
    #: Patrones ``fnmatch`` de nombres que no escanea ningún proyecto de esta ubicación de origen (1.4.0).
    ignore_patterns: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")
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


class AiSetting(Base):
    """Campo de una familia de IA guardado por un admin (Fase 8, ADR-004); sin fila, vale ``DOC_ORGANIZE_*``.

    Desde doc_organize 2.0 (migración ``0016``) las familias son ``litellm`` (todas las tareas: URL y clave generales y,
    por tarea, ``model_<tarea>``, ``virtual_key_<tarea>`` y ``budget_<tarea>``), ``litellm_usage`` y
    ``github_copilot_usage``. Las filas de 1.x quedan en ``ai_settings_v1`` solo para la bajada.

    De instancia (como en la web integrada): los tenants llegan en la Fase 9. Un campo secreto solo se guarda cifrado
    con MultiFernet en ``ciphertext``; uno no secreto, en claro en ``value``. Nunca los dos.
    """

    __tablename__ = "ai_settings"
    __table_args__ = (CheckConstraint("(value IS NULL) <> (ciphertext IS NULL)", name="one_value"),)

    family: Mapped[str] = mapped_column(String(64), primary_key=True)
    field: Mapped[str] = mapped_column(String(32), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text, default=None)
    ciphertext: Mapped[str | None] = mapped_column(Text, default=None)
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
    __table_args__ = (
        CheckConstraint("status IN ('active', 'deleted')", name="status"),
        CheckConstraint("context_versions IN ('all', 'mark', 'current_only')", name="context_versions"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True, default=DEFAULT_TENANT_ID)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(String(1024), default=None)
    source_location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"), index=True)
    source_subpaths: Mapped[list[str]] = mapped_column(JSON)
    destination_location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"), index=True)
    destination_subpath: Mapped[str] = mapped_column(String(4096))
    #: Guardar la cuenta propietaria de cada fichero al escanear (1.5.0, ``ScanOptions.capture_owner``): dato personal,
    #: solo lo activa el ``owner`` y es fijo por proyecto para que un escaneo no lo borre por olvidar la opción.
    capture_owner: Mapped[bool] = mapped_column(default=False, server_default=false())
    #: doc_organize 2.0 (migración ``0017``): redactar credenciales de lo que sale hacia la IA (D7), qué hacer con las
    #: versiones de un documento al construir el contexto (D8: ``mark`` en la web) y sub-fase semántica (D13, opt-in).
    ai_redact_credentials: Mapped[bool] = mapped_column(default=True, server_default=true())
    context_versions: Mapped[str] = mapped_column(String(16), default="mark", server_default="mark")
    context_semantic: Mapped[bool] = mapped_column(default=False, server_default=false())
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
    #: Por qué se pidió parar: ``user`` (cancelación) o ``timeout`` (el worker agota el tiempo y pide una parada
    #: ordenada antes de terminar el subproceso, para que la operación guarde lo hecho).
    cancel_reason: Mapped[str | None] = mapped_column(String(16), default=None)
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
    #: Memoria del contenedor (cgroup), OOM y tramos del escaneo, del último latido (Fase 10).
    resources: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)


class PeriodicTask(Base):
    """Marca de la última ejecución de una tarea periódica del worker; con varios workers solo uno la reclama."""

    __tablename__ = "periodic_tasks"

    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    last_run_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), default=None)
    claimed_by: Mapped[str | None] = mapped_column(String(128), default=None)


class ScannedFolder(Base):
    """Estado de una carpeta de origen del proyecto (``projects.source_subpaths``) en los escaneos (Fase 4).

    Sustituye a ``ScannedFoldersStore`` (JSON) de la web integrada. ``used`` es permanente: la carpeta ya se escaneó
    alguna vez, así que tiene salidas en el destino.
    """

    __tablename__ = "scanned_folders"

    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    subpath: Mapped[str] = mapped_column(String(4096), primary_key=True)
    used: Mapped[bool] = mapped_column(default=False)
    added_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)
    added_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    last_scanned_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), default=None)
    last_run_id: Mapped[str | None] = mapped_column(ForeignKey("runs.id", ondelete="SET NULL"), default=None)
    #: Subcarpetas que el escaneo no recorre (1.4.0), relativas a esta carpeta y tal como las da el resolvedor.
    excluded_subpaths: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")


class ScanError(Base):
    """Documento que no se pudo convertir en un run ``scan`` (``ScanErrorReport`` de doc_organize).

    ``path`` es relativa a la ubicación de origen y ``message`` ya está saneado (sin rutas del contenedor).
    """

    __tablename__ = "scan_errors"
    __table_args__ = (Index("ix_scan_errors_project_run", "project_id", "run_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    path: Mapped[str] = mapped_column(String(4096))
    message: Mapped[str] = mapped_column(String(2000))
    retry_count: Mapped[int] = mapped_column(Integer, default=1)
    capped: Mapped[bool] = mapped_column(default=False)


class DuplicateGroupRow(Base):
    """Grupo de duplicados de un run ``dedup_preview`` (``DuplicateGroup`` de doc_organize, Fase 6).

    ``members`` lleva rutas relativas a la ubicación de origen (``folder`` + ``path``), tamaño, fecha, hash y si es el
    canónico (el que doc_organize conserva por defecto). Se borra con el run.
    """

    __tablename__ = "duplicate_groups"
    __table_args__ = (Index("ix_duplicate_groups_run_reason_position", "run_id", "reason", "position"),)

    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), primary_key=True)
    group_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    reason: Mapped[str] = mapped_column(String(32))
    position: Mapped[int] = mapped_column(Integer)
    member_count: Mapped[int] = mapped_column(Integer)
    members: Mapped[list[dict[str, Any]]] = mapped_column(JSON)


class TaxonomyTemplate(Base):
    """Plantilla de taxonomía personalizada (Fase 7): Markdown con front matter que valida doc_organize.

    Las plantillas incluidas en doc_organize no se copian aquí: se leen de la librería y sus nombres no se pueden usar
    (decisión C2 del mantenedor). ``title`` y ``description`` repiten los del front matter para listar sin parsear.
    """

    __tablename__ = "taxonomy_templates"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_taxonomy_templates_tenant_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True, default=DEFAULT_TENANT_ID)
    name: Mapped[str] = mapped_column(String(64))
    title: Mapped[str | None] = mapped_column(String(256), default=None)
    description: Mapped[str | None] = mapped_column(String(1024), default=None)
    markdown: Mapped[str] = mapped_column(Text)
    #: Texto de 1.x que la migración ``0017`` pasó al formato 2.0 (``markdown``); nulo si ya era 2.0.
    markdown_v1: Mapped[str | None] = mapped_column(Text, default=None)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


class ProjectContext(Base):
    """Resumen del último contexto construido del proyecto (Fase 7, decisión C3).

    Proyección de ``context.json`` (que vive en el destino) que escribe el run ``context_build`` al terminar y borra
    ``context_delete``: la API lista y pagina sin leer la ubicación de red en cada petición. ``domains`` lleva, por
    dominio, ``slug``, ``name``, ``description``, ``status`` y ``documents``.
    """

    __tablename__ = "project_contexts"

    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    output_folder_name: Mapped[str] = mapped_column(String(255))
    catalog_kind: Mapped[str] = mapped_column(String(16))
    taxonomy_template_name: Mapped[str | None] = mapped_column(String(64), default=None)
    documents_count: Mapped[int] = mapped_column(Integer, default=0)
    unclassified_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    collisions_count: Mapped[int] = mapped_column(Integer, default=0)
    site_built: Mapped[bool] = mapped_column(default=False)
    #: Se construyó con la Sub-fase B (IA, Fase 8).
    ai_classification: Mapped[bool] = mapped_column(default=False)
    #: Trazabilidad (1.5.0): versión de doc_organize y modelos de IA de la construcción; nulos en contextos anteriores.
    built_with_version: Mapped[str | None] = mapped_column(String(128), default=None)
    ai_classification_model: Mapped[str | None] = mapped_column(String(128), default=None)
    ai_enrichment_model: Mapped[str | None] = mapped_column(String(128), default=None)
    domains: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    #: Ejes del contexto (doc_organize 2.0, ``Context.taxonomy_axes``): ``key``, ``name``, ``description``,
    #: ``multiple``, ``organizes`` y ``values`` (``slug``, ``name``), sin palabras clave ni ejemplos.
    taxonomy_axes: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, server_default="[]")
    built_by_run_id: Mapped[str | None] = mapped_column(ForeignKey("runs.id", ondelete="SET NULL"), default=None)
    built_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


ManifestVersionAction = Literal["save", "delete", "restore", "history_clear"]


class ProjectManifestVersion(Base):
    """Versión anterior de ``taxonomy_manifest.md`` (1.8.0): lo que había **antes** de guardar, borrar, restaurar o
    vaciar el histórico, para poder deshacerlo. ``markdown`` nulo = no había manifiesto.

    Se conservan las ``MAX_MANIFEST_VERSIONS`` últimas por proyecto (``app/domain/context/manifest_versions.py``).
    ``domains`` y ``material_types`` son los recuentos del catálogo de esa versión, nulos si no era válida. Los
    proyectos se borran de forma lógica: las versiones solo se van con el proyecto si alguna vez se purga.
    """

    __tablename__ = "project_manifest_versions"
    __table_args__ = (
        CheckConstraint("action IN ('save', 'delete', 'restore', 'history_clear')", name="action"),
        Index("ix_project_manifest_versions_project_created", "project_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), default=None)
    action: Mapped[str] = mapped_column(String(16))
    markdown: Mapped[str | None] = mapped_column(Text, default=None)
    domains: Mapped[int | None] = mapped_column(Integer, default=None)
    material_types: Mapped[int | None] = mapped_column(Integer, default=None)


class ContextDocument(Base):
    """Documento del contexto (Fase 7): clasificado en un dominio o, con ``domain_slug`` nulo, sin clasificar.

    Rutas relativas: ``folder`` + ``path`` del original en el origen y ``organized_path`` de la copia dentro de la
    carpeta del proyecto en el destino (nula si no se copió). ``failed`` marca los que doc_organize no pudo copiar (G27)
    y ``collision`` los que compartían carpeta con otro y se sobrescribían en la copia (G30, contextos construidos con
    doc_organize 0.13.0; desde 0.14.0 ya no ocurre).
    """

    __tablename__ = "context_documents"
    __table_args__ = (
        Index("ix_context_documents_project_domain", "project_id", "domain_slug", "seq"),
        Index("ix_context_documents_project_language", "project_id", "language"),
    )

    project_id: Mapped[int] = mapped_column(
        ForeignKey("project_contexts.project_id", ondelete="CASCADE"), primary_key=True
    )
    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    domain_slug: Mapped[str | None] = mapped_column(String(128), default=None)
    title: Mapped[str] = mapped_column(String(1024))
    document_type: Mapped[str | None] = mapped_column(String(64), default=None)
    material_type: Mapped[str | None] = mapped_column(String(128), default=None)
    material_type_name: Mapped[str | None] = mapped_column(String(256), default=None)
    folder: Mapped[str] = mapped_column(String(4096))
    path: Mapped[str] = mapped_column(String(4096))
    organized_path: Mapped[str | None] = mapped_column(String(4096), default=None)
    failed: Mapped[bool] = mapped_column(default=False)
    collision: Mapped[bool] = mapped_column(default=False)
    #: ``rules`` o ``ai`` (quién lo clasificó, Fase 8); nulo si no se clasificó.
    classified_by: Mapped[str | None] = mapped_column(String(8), default=None)
    # 1.5.0 (doc_organize 1.5.0): propiedades del documento y trazabilidad de la clasificación. Nulos (o ``[]``) en
    # contextos anteriores hasta reconstruir.
    author: Mapped[str | None] = mapped_column(String(500), default=None)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")
    language: Mapped[str | None] = mapped_column(String(8), default=None)
    #: Campos que rellenó la IA (``description``, ``keywords``) porque el documento no los declaraba.
    ai_filled: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")
    rules_domain: Mapped[str | None] = mapped_column(String(128), default=None)
    rules_confidence: Mapped[float | None] = mapped_column(Float, default=None)
    ai_domain: Mapped[str | None] = mapped_column(String(128), default=None)
    ai_confidence: Mapped[float | None] = mapped_column(Float, default=None)
    ai_reasoning: Mapped[str | None] = mapped_column(String(500), default=None)
    material_type_confidence: Mapped[float | None] = mapped_column(Float, default=None)
    #: Por qué no se clasificó (1.6.0, G42): ``incomplete_artifacts`` (sin ``.md`` o ``.json``) o ``below_threshold``
    #: (las reglas no llegan al umbral y la IA no lo asignó). Nulo si está clasificado o en contextos anteriores.
    unclassified_reason: Mapped[str | None] = mapped_column(String(32), default=None)


class ContextDocumentAxisValue(Base):
    """Un valor de un eje de un documento del contexto (doc_organize 2.0, ``AxisValue``; migración ``0017``, U3).

    Tabla **genérica** para todos los ejes (dominio, tipo de material y los que solo etiquetan), indexada para filtrar y
    contar por ``(project_id, axis, slug)``. ``context_documents.domain_slug``/``material_type`` repiten los de los ejes
    organizadores. ``classified_by``: ``rules``, ``semantic``, ``ai`` o ``human``; ``evidence_verified`` nulo sin cita.
    """

    __tablename__ = "context_document_axis_values"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "seq"],
            ["context_documents.project_id", "context_documents.seq"],
            name="document",
            ondelete="CASCADE",
        ),
        Index("ix_context_document_axis_values_project_axis_slug", "project_id", "axis", "slug"),
    )

    project_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    axis: Mapped[str] = mapped_column(String(41), primary_key=True)
    slug: Mapped[str] = mapped_column(String(128), primary_key=True)
    name: Mapped[str] = mapped_column(String(256))
    confidence: Mapped[float | None] = mapped_column(Float, default=None)
    classified_by: Mapped[str | None] = mapped_column(String(8), default=None)
    evidence_verified: Mapped[bool | None] = mapped_column(default=None)
