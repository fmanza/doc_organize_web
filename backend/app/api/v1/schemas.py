"""Esquemas HTTP de la API v1. Las contraseñas son solo de entrada (``SecretStr``) y nunca salen en respuestas."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from app.domain.identity.passwords import MAX_PASSWORD_LENGTH

Role = Literal["admin", "user"]
Username = Annotated[str, Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")]
DisplayName = Annotated[str, Field(min_length=1, max_length=128)]
Password = Annotated[SecretStr, Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)]

MAX_PAGE_SIZE = 200


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- auth -------------------------------------------------------------------------------------------------------


class CsrfToken(BaseModel):
    """Token CSRF para la cabecera ``X-CSRF-Token``."""

    csrf_token: str


class LoginRequest(BaseModel):
    """Credenciales de inicio de sesión."""

    username: Annotated[str, Field(min_length=1, max_length=64)]
    password: Password


class PasswordChange(BaseModel):
    """Cambio de la propia contraseña."""

    current_password: Password
    new_password: Password


class Me(_Out):
    """Usuario de la sesión actual."""

    id: int
    username: str
    display_name: str
    role: Role


# --- users ------------------------------------------------------------------------------------------------------


class UserOut(_Out):
    """Usuario visto por un administrador."""

    id: int
    username: str
    display_name: str
    role: Role
    is_active: bool
    locked_until: datetime | None
    failed_attempts: int
    password_changed_at: datetime
    created_at: datetime
    updated_at: datetime


class UserCreate(BaseModel):
    """Alta de usuario."""

    username: Username
    display_name: DisplayName
    password: Password
    role: Role = "user"


class UserUpdate(BaseModel):
    """Edición parcial de usuario; ``password`` restablece la contraseña y cierra sus sesiones; ``unlock`` quita el
    bloqueo por intentos fallidos."""

    display_name: DisplayName | None = None
    role: Role | None = None
    is_active: bool | None = None
    password: Password | None = None
    unlock: bool = False


class UserPage(BaseModel):
    """Página de usuarios."""

    items: list[UserOut]
    total: int


# --- sessions ---------------------------------------------------------------------------------------------------


class SessionOut(_Out):
    """Sesión activa; nunca incluye el token."""

    id: int
    user_id: int
    username: str
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    ip: str | None
    user_agent: str | None
    current: bool


class SessionPage(BaseModel):
    """Página de sesiones."""

    items: list[SessionOut]
    total: int


# --- audit ------------------------------------------------------------------------------------------------------


class AuditEntryOut(_Out):
    """Evento de auditoría."""

    id: int
    ts: datetime
    actor_user_id: int | None
    actor_username: str | None
    action: str
    outcome: str
    target_type: str | None
    target_id: str | None
    ip: str | None
    details: dict[str, object] | None


class AuditPage(BaseModel):
    """Página de auditoría."""

    items: list[AuditEntryOut]
    total: int


# --- locations --------------------------------------------------------------------------------------------------

LocationName = Annotated[str, Field(min_length=1, max_length=128)]
DisplayPath = Annotated[str, Field(max_length=1024)]
RelativePath = Annotated[str, Field(max_length=4096, description="Ruta relativa con «/»; vacía = la raíz")]
LocationKind = Literal["local", "network"]
LocationUsage = Literal["source", "destination", "both"]
LocationAccess = Literal["ro", "rw"]
LocationStatus = Literal["unknown", "ok", "degraded", "unavailable"]
MAX_FOLDER_PAGE = 500


class LocationPublic(_Out):
    """Ubicación vista por cualquier usuario: sin la ruta del contenedor."""

    id: int
    name: str
    display_path: str | None
    kind: LocationKind
    usage: LocationUsage
    access: LocationAccess
    status: LocationStatus
    status_reasons: list[str] | None
    probed_at: datetime | None


class LocationOut(LocationPublic):
    """Ubicación vista por un administrador."""

    container_path: str
    latency_ms: float | None
    free_bytes: int | None
    writable: bool | None
    created_at: datetime
    updated_at: datetime


class LocationCreate(BaseModel):
    """Alta de ubicación. ``path`` es relativa a ``DOW_LOCATIONS_ROOT`` (``/mnt``) y no se puede cambiar después."""

    name: LocationName
    path: RelativePath
    display_path: DisplayPath | None = None
    kind: LocationKind = "local"
    usage: LocationUsage
    access: LocationAccess = "ro"


class LocationUpdate(BaseModel):
    """Edición parcial de ubicación (la carpeta del contenedor no se puede cambiar)."""

    model_config = ConfigDict(extra="forbid")

    name: LocationName | None = None
    display_path: DisplayPath | None = None
    kind: LocationKind | None = None
    usage: LocationUsage | None = None
    access: LocationAccess | None = None


class LocationPage(BaseModel):
    """Página de ubicaciones (``LocationOut`` para admin, ``LocationPublic`` para el resto)."""

    items: list[LocationOut | LocationPublic]
    total: int


class FolderEntry(BaseModel):
    """Subcarpeta: nombre y ruta relativa a la raíz explorada."""

    name: str
    path: str


class FolderListing(BaseModel):
    """Subcarpetas de una carpeta, paginadas."""

    location_id: int | None
    path: str
    parent: str | None
    items: list[FolderEntry]
    total: int


# --- settings ---------------------------------------------------------------------------------------------------


class SettingOut(BaseModel):
    """Ajuste administrable con su valor efectivo, el que tendría sin cambio en la web y su origen."""

    key: str
    value: int
    default: int
    source: Literal["db", "env", "default"]


class SettingsPage(BaseModel):
    """Ajustes administrables."""

    items: list[SettingOut]


class SettingsUpdate(BaseModel):
    """Cambios de ajustes: ``clave → valor``; ``null`` vuelve al valor de la variable ``DOW_*`` o por defecto."""

    values: dict[str, int | None]


# --- instance ---------------------------------------------------------------------------------------------------


class CapabilitiesOut(BaseModel):
    """Capacidades de la instancia para convertir documentos."""

    gpu_support_installed: bool
    gpu_active: bool
    asr_installed: bool
    ffmpeg_installed: bool
    av_ready: bool
    libreoffice_installed: bool


class InstanceCapabilities(BaseModel):
    """Ficha de capacidades publicada por los workers: ``pending`` mientras el worker vivo no las ha calculado;
    ``no_worker`` si no hay worker vivo (con las últimas conocidas, si las hay)."""

    status: Literal["ok", "pending", "no_worker"]
    checked_at: datetime | None
    capabilities: CapabilitiesOut | None
    queues: list[str]
    doc_organize_version: str | None


class WorkerOut(_Out):
    """Worker registrado (solo admin)."""

    id: str
    queues: list[str]
    version: str
    doc_organize_version: str | None
    started_at: datetime
    heartbeat_at: datetime
    alive: bool
    capabilities_at: datetime | None


class WorkerList(BaseModel):
    """Workers registrados."""

    items: list[WorkerOut]


# --- projects ---------------------------------------------------------------------------------------------------

ProjectName = Annotated[str, Field(min_length=1, max_length=128)]
MemberRole = Literal["owner", "editor", "viewer"]
RunStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]
Operation = Literal["noop", "history_clear", "project_move", "project_delete"]


class LocationRef(_Out):
    """Ubicación referida por un proyecto: nombre y estado, nunca la ruta del contenedor."""

    id: int
    name: str
    access: LocationAccess
    status: LocationStatus


class RunBrief(_Out):
    """Resumen de un run para listas."""

    id: str
    operation: Operation
    status: RunStatus
    created_at: datetime
    finished_at: datetime | None


class ProjectOut(BaseModel):
    """Proyecto con las rutas relativas a sus ubicaciones y el rol del usuario."""

    id: int
    name: str
    description: str | None
    source_location: LocationRef
    source_subpaths: list[str]
    destination_location: LocationRef
    destination_subpath: str
    role: MemberRole
    created_at: datetime
    updated_at: datetime
    last_run: RunBrief | None = None
    active_run: bool = False


class ProjectPage(BaseModel):
    """Página de proyectos."""

    items: list[ProjectOut]
    total: int


class ProjectCreate(BaseModel):
    """Alta de proyecto. La carpeta de salidas es ``destination_parent/new_folder`` (nueva) o, sin ``new_folder``,
    ``destination_parent`` (que debe estar vacía)."""

    model_config = ConfigDict(extra="forbid")

    name: ProjectName
    description: Annotated[str, Field(max_length=1024)] | None = None
    source_location_id: int = Field(ge=1)
    source_subpaths: list[RelativePath] = Field(min_length=1, max_length=20)
    destination_location_id: int = Field(ge=1)
    destination_parent: RelativePath = ""
    new_folder: Annotated[str, Field(min_length=1, max_length=120)] | None = None


class ProjectUpdate(BaseModel):
    """Edición parcial: renombrar (solo en la BD), descripción y carpetas de origen."""

    model_config = ConfigDict(extra="forbid")

    name: ProjectName | None = None
    description: Annotated[str, Field(max_length=1024)] | None = None
    source_subpaths: list[RelativePath] | None = Field(default=None, min_length=1, max_length=20)


class MemberOut(BaseModel):
    """Miembro de un proyecto."""

    user_id: int
    username: str
    display_name: str
    role: MemberRole
    added_at: datetime


class MemberList(BaseModel):
    """Miembros de un proyecto."""

    items: list[MemberOut]


class MemberCreate(BaseModel):
    """Alta de miembro."""

    user_id: int = Field(ge=1)
    role: MemberRole = "viewer"


class MemberUpdate(BaseModel):
    """Cambio de rol de un miembro."""

    role: MemberRole


class UserBrief(_Out):
    """Usuario activo para invitar a un proyecto."""

    id: int
    username: str
    display_name: str


class UserLookup(BaseModel):
    """Resultado de la búsqueda de usuarios."""

    items: list[UserBrief]


# --- runs -------------------------------------------------------------------------------------------------------


class ArtifactOut(_Out):
    """Fichero de un run, descargable mientras no lo purgue la retención."""

    id: int
    name: str
    kind: Literal["log", "output", "report"]
    size_bytes: int
    content_type: str
    created_at: datetime


class RunProgress(BaseModel):
    """Último progreso publicado."""

    phase: str
    processed: int
    total: int | None = None
    current: str | None = None


class RunOut(BaseModel):
    """Ejecución con su estado, progreso, resultado y artefactos."""

    id: str
    project_id: int | None
    project_name: str | None
    operation: Operation
    queue: Literal["cpu", "gpu"]
    status: RunStatus
    is_write: bool
    params: dict[str, Any]
    progress: RunProgress | None
    result: dict[str, Any] | None
    error_code: str | None
    error_message: str | None
    cancel_requested: bool
    created_by_username: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    workspace_purged: bool
    artifacts: list[ArtifactOut]
    can_cancel: bool


class RunPage(BaseModel):
    """Página del historial de ejecuciones."""

    items: list[RunOut]
    total: int
