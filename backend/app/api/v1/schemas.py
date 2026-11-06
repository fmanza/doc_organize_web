"""Esquemas HTTP de la API v1. Las contraseñas son solo de entrada (``SecretStr``) y nunca salen en respuestas."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from app.domain.identity.passwords import MAX_PASSWORD_LENGTH

Permission = Literal[
    "users.manage", "roles.manage", "audit.read", "templates.manage", "projects.create", "projects.all"
]
TenantSlug = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9-]{1,62}$")]
RoleName = Annotated[str, Field(min_length=1, max_length=64)]
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


class TenantRef(_Out):
    id: int
    slug: str
    name: str


class RoleRef(_Out):
    id: int
    name: str
    builtin: Literal["admin", "user"] | None


class Me(BaseModel):
    """Usuario de la sesión actual: su tenant, el tenant en el que actúa (distinto solo para un admin de instancia que
    lo cambió con el selector), su rol y sus permisos en el tenant activo (Fase 9)."""

    id: int
    username: str
    display_name: str
    tenant: TenantRef
    acting_tenant: TenantRef
    is_instance_admin: bool
    role: RoleRef
    permissions: list[Permission]


# --- users ------------------------------------------------------------------------------------------------------


class UserOut(_Out):
    """Usuario visto por quien gestiona usuarios."""

    id: int
    username: str
    display_name: str
    tenant_id: int
    role: RoleRef
    is_instance_admin: bool
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
    role_id: int | None = Field(default=None, description="Rol del tenant; sin él, «Usuario»")
    is_instance_admin: bool = Field(default=False, description="Solo lo da un administrador de la instancia")
    tenant_id: int | None = Field(default=None, description="Solo el admin de instancia; sin él, el tenant activo")


class UserUpdate(BaseModel):
    """Edición parcial de usuario; ``password`` restablece la contraseña y cierra sus sesiones; ``unlock`` quita el
    bloqueo por intentos fallidos."""

    display_name: DisplayName | None = None
    role_id: int | None = None
    is_instance_admin: bool | None = None
    tenant_id: int | None = Field(
        default=None, description="Mover a otro tenant (solo admin de instancia): pierde sus proyectos y sesiones"
    )
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
    tenant_id: int | None = Field(default=None, description="Pasarla a otro tenant (si ningún proyecto la usa)")


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
    models_ready: bool = False
    picture_description_ready: bool = False
    gpu_ready: bool = False


class ScanOptionsAvailability(BaseModel):
    """Opciones de escaneo que algún worker vivo de su cola puede atender ahora (la API lo vuelve a comprobar)."""

    use_gpu: bool
    include_audio_video: bool
    use_picture_description: bool


class InstanceCapabilities(BaseModel):
    """Ficha de capacidades publicada por los workers: ``pending`` mientras el worker vivo no las ha calculado;
    ``no_worker`` si no hay worker vivo (con las últimas conocidas, si las hay)."""

    status: Literal["ok", "pending", "no_worker"]
    checked_at: datetime | None
    capabilities: CapabilitiesOut | None
    queues: list[str]
    capability_queues: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Por cada capacidad que algún worker vivo tiene, las colas de esos workers (p. ej. gpu_ready → gpu)",
    )
    doc_organize_version: str | None
    scan_options: ScanOptionsAvailability


class WorkerResources(BaseModel):
    """Memoria del contenedor del worker (cgroup), huecos de jobs y ajustes del escaneo, del último latido; ``None`` =
    desconocido (un worker anterior a la 1.1.0) o sin límite. ``memory_peak_bytes`` cuenta desde que arrancó el
    contenedor."""

    memory_limit_bytes: int | None = None
    memory_peak_bytes: int | None = None
    memory_current_bytes: int | None = None
    oom_kills: int | None = None
    slots: int | None = Field(default=None, description="Jobs simultáneos del worker (DOW_WORKER_CONCURRENCY)")
    scan_recycle_documents: int | None = None
    scan_document_timeout_seconds: int | None = Field(default=None, description="0 = sin límite")
    scan_io_retries: int | None = None
    scan_reuse_hashes: bool | None = None


class WorkerOut(_Out):
    """Worker registrado (solo admin), con su GPU y sus recursos (Fase 10)."""

    id: str
    queues: list[str]
    version: str
    doc_organize_version: str | None
    started_at: datetime
    heartbeat_at: datetime
    alive: bool
    capabilities_at: datetime | None
    gpu_ready: bool | None = None
    resources: WorkerResources | None = None
    running: int = Field(default=0, description="Ejecuciones que este worker tiene en marcha ahora")


class WorkerList(BaseModel):
    """Workers registrados."""

    items: list[WorkerOut]


# --- projects ---------------------------------------------------------------------------------------------------

ProjectName = Annotated[str, Field(min_length=1, max_length=128)]
MemberRole = Literal["owner", "editor", "viewer"]
RunStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]
Operation = Literal[
    "noop",
    "history_clear",
    "project_move",
    "project_delete",
    "scan",
    "export_zip",
    "export_xlsx",
    "search_index",
    "dedup_preview",
    "dedup_apply",
    "context_build",
    "context_delete",
    "taxonomy_draft",
]


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


# --- escaneo (Fase 4) --------------------------------------------------------------------------------------------


class ScannedFolderOut(_Out):
    """Carpeta de origen del proyecto con su estado en los escaneos (ruta relativa a la ubicación de origen)."""

    subpath: str
    used: bool
    added_at: datetime
    last_scanned_at: datetime | None
    last_run_id: str | None
    available: bool


class ScannedFolderList(BaseModel):
    """Carpetas de origen del proyecto y su ubicación."""

    location: LocationRef
    items: list[ScannedFolderOut]


class ScannedFolderCreate(BaseModel):
    """Carpeta de origen nueva, relativa a la ubicación de origen del proyecto."""

    subpath: str = Field(max_length=4096)


class ScannedFolderRemoved(BaseModel):
    """Resultado de quitar una carpeta: si ya se había escaneado, sus salidas siguen en el destino."""

    subpath: str
    used: bool


class ScanErrorOut(_Out):
    """Documento que no se pudo convertir (ruta relativa a la ubicación de origen, mensaje sin rutas del contenedor)."""

    id: int
    path: str
    message: str
    retry_count: int
    capped: bool


class ScanErrorPage(BaseModel):
    """Página de errores de un escaneo; ``run`` es el escaneo al que pertenecen (``None`` si aún no hay ninguno)."""

    run: RunBrief | None
    items: list[ScanErrorOut]
    total: int


# --- documentos, visor y búsqueda (Fase 5) -----------------------------------------------------------------------


class DocumentOut(_Out):
    """Documento de la caché del proyecto, con rutas relativas a su carpeta de origen (nunca del servidor)."""

    folder: str = Field(description="Carpeta de origen («» = la raíz de la ubicación)")
    path: str = Field(description="Ruta del documento relativa a su carpeta")
    status: str = Field(description="new, modified, unchanged o deleted")
    conversion_status: str | None = Field(description="success, error, pending, in_progress, ocr_pending…")
    error_message: str | None
    error_retry_count: int
    updated_at: datetime
    output_path: str | None = Field(description="Markdown convertido, relativo a Conversión/ (para el visor)")


class DocumentPage(BaseModel):
    """Página de documentos del proyecto."""

    items: list[DocumentOut]
    total: int


class SearchHitOut(_Out):
    """Documento convertido que contiene las palabras buscadas."""

    output_path: str = Field(description="Markdown relativo a Conversión/")
    title: str
    snippet: str = Field(description="Fragmento; las coincidencias van entre U+0002 y U+0003 (texto, nunca HTML)")


class SearchPage(BaseModel):
    """Resultados de la búsqueda de texto completo; ``indexed_at`` es ``None`` si aún no hay índice."""

    items: list[SearchHitOut]
    total: int
    indexed_at: datetime | None


# --- duplicados (Fase 6) -----------------------------------------------------------------------------------------


class DuplicateMemberOut(BaseModel):
    """Documento de un grupo de duplicados, con ruta relativa a su carpeta de origen."""

    key: str = Field(description="«<carpeta>/<ruta>»: valor de «keep» para conservarlo al aplicar")
    folder: str
    path: str
    size_bytes: int
    modified_at: datetime
    sha256: str
    canonical: bool = Field(description="El que se conserva por defecto (el más antiguo)")
    output_path: str | None = Field(description="Markdown convertido, relativo a Conversión/ (para el visor)")


class DuplicateGroupOut(BaseModel):
    """Grupo de duplicados de una vista previa."""

    group_id: str
    reason: Literal["exact_duplicate", "version_conflict", "fuzzy_name_match"]
    members: list[DuplicateMemberOut]


class DuplicateGroupPage(BaseModel):
    """Página de grupos de una vista previa de duplicados."""

    run: RunBrief
    items: list[DuplicateGroupOut]
    total: int


class DuplicatesLastOut(BaseModel):
    """Última búsqueda de duplicados y última aplicación real del proyecto (``None`` si no hay)."""

    preview: RunBrief | None
    apply: RunBrief | None


# --- Fase 7: contexto y taxonomías ----------------------------------------------------------------------------------


class CatalogEntryOut(BaseModel):
    """Dominio o tipo de material de una plantilla o manifiesto."""

    slug: str
    name: str


class TaxonomyTemplateOut(BaseModel):
    """Plantilla de taxonomía en el listado: ``builtin`` = incluida en doc_organize (solo lectura)."""

    name: str
    title: str | None
    description: str | None
    builtin: bool
    updated_at: datetime | None = None


class TaxonomyTemplateList(BaseModel):
    items: list[TaxonomyTemplateOut]


class TaxonomyTemplateDetail(TaxonomyTemplateOut):
    """Plantilla con su Markdown y su catálogo."""

    markdown: str
    domains: list[CatalogEntryOut]
    material_types: list[CatalogEntryOut]


class TaxonomyMarkdownIn(BaseModel):
    """Markdown de una plantilla o manifiesto: front matter YAML (``domains``, ``material_types``) y prosa."""

    model_config = ConfigDict(extra="forbid")

    markdown: str = Field(min_length=1, max_length=262_144)


class TaxonomyManifestOut(BaseModel):
    """``taxonomy_manifest.md`` del proyecto: ``markdown`` nulo si no existe; ``error`` si no es válido."""

    markdown: str | None
    error: str | None = None
    domains: list[CatalogEntryOut] = []
    material_types: list[CatalogEntryOut] = []


class ContextDomainOut(BaseModel):
    slug: str
    name: str
    description: str | None
    status: str
    documents: int


class ContextOut(BaseModel):
    """Resumen del contexto construido del proyecto (proyección del último ``context_build``)."""

    output_folder_name: str
    catalog_kind: str
    taxonomy_template_name: str | None
    documents_count: int
    unclassified_count: int
    failed_count: int
    collisions_count: int
    site_built: bool
    ai_classification: bool = False
    domains: list[ContextDomainOut]
    built_by_run_id: str | None
    built_at: datetime


class ContextDocumentOut(_Out):
    """Documento del contexto: original (``folder`` + ``path``) y copia relativa a la carpeta del proyecto."""

    title: str
    domain_slug: str | None
    document_type: str | None
    material_type: str | None
    material_type_name: str | None
    folder: str
    path: str
    organized_path: str | None
    failed: bool
    collision: bool
    classified_by: Literal["rules", "ai"] | None = None
    output_path: str | None = None


class ContextDocumentPage(BaseModel):
    items: list[ContextDocumentOut]
    total: int


class SiteSessionOut(BaseModel):
    """URL del sitio aislado (con su token) y su caducidad."""

    url: str
    expires_at: datetime


# --- ai (Fase 8) -------------------------------------------------------------------------------------------------

AiFamilyKey = Literal[
    "litellm_classification",
    "litellm_taxonomy_classification",
    "litellm_taxonomy_manifest_draft",
    "litellm_usage",
    "github_copilot_usage",
]


class AiFieldOut(BaseModel):
    """Campo de una familia de IA. ``value`` solo en los no secretos; ``hint`` («…ab12» o «***») solo en los secretos."""

    name: str
    env_var: str
    secret: bool
    required: bool
    source: Literal["db", "env", "none"]
    value: str | None
    hint: str | None
    undecryptable: bool = Field(description="Hay un valor guardado que no se descifra con las claves actuales")


class AiFamilyOut(BaseModel):
    key: AiFamilyKey
    configured: bool = Field(description="Tiene todos sus campos obligatorios")
    fields: list[AiFieldOut]


class AiSettingsOut(BaseModel):
    """Configuración de IA de la instancia, sin ningún secreto."""

    encryption_configured: bool
    families: list[AiFamilyOut]


class AiFamilyUpdate(BaseModel):
    """Campos que cambian: ausente = no se toca; ``null`` o ``""`` = borrar el valor guardado (vuelve al entorno)."""

    model_config = ConfigDict(extra="forbid")

    fields: dict[Annotated[str, Field(max_length=32)], Annotated[str, Field(max_length=4096)] | None] = Field(
        max_length=8
    )


class AiStatusOut(BaseModel):
    """Qué familias de IA están configuradas (para cualquier usuario, sin valores)."""

    families: dict[str, bool]


class AiUsageItemOut(BaseModel):
    date: str
    product: str
    sku: str | None
    quantity: float
    unit_type: str
    cost_usd: float | None


class AiUsageSourceOut(BaseModel):
    """Uso de una fuente en el periodo actual, o por qué no hay (sin configurar o ``error``)."""

    source: Literal["litellm", "github_copilot"]
    configured: bool
    fetched_at: datetime | None
    cached: bool
    period_start: str | None
    period_end: str | None
    total_cost_usd: float | None
    items: list[AiUsageItemOut]
    error: Literal["ai_auth", "ai_connection", "ai_error"] | None


class AiUsageOut(BaseModel):
    sources: list[AiUsageSourceOut]


# --- tenants y roles (Fase 9) ----------------------------------------------------------------------------------


class TenantOut(BaseModel):
    """Tenant con sus recuentos (``empty``: se puede borrar)."""

    id: int
    slug: str
    name: str
    created_at: datetime
    users: int
    projects: int
    locations: int
    empty: bool


class TenantPage(BaseModel):
    items: list[TenantOut]
    total: int


class TenantCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: TenantSlug
    name: Annotated[str, Field(min_length=1, max_length=128)]


class TenantUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=1, max_length=128)]


class TenantSwitch(BaseModel):
    """Tenant en el que actuar (``null``: el propio)."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: int | None


class RoleOut(BaseModel):
    id: int
    name: str
    builtin: Literal["admin", "user"] | None
    permissions: list[Permission]
    users: int
    created_at: datetime
    updated_at: datetime


class RoleList(BaseModel):
    items: list[RoleOut]


class RoleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: RoleName
    permissions: list[str] = Field(default_factory=list, max_length=32)


class RoleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: RoleName | None = None
    permissions: list[str] | None = Field(default=None, max_length=32)


class PermissionList(BaseModel):
    """Catálogo de permisos de los roles, en orden."""

    items: list[Permission]
