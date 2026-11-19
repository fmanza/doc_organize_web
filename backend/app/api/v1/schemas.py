"""Esquemas HTTP de la API v1. Las contraseñas son solo de entrada (``SecretStr``) y nunca salen en respuestas."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, SecretStr

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


class AuditPurgeIn(BaseModel):
    """Borrar la auditoría del tenant activo en ``[since, until)`` (web 1.2.0, solo el admin de instancia).

    Primero con ``dry_run`` (cuenta las entradas); después sin él y con ``confirm_count`` igual a esa cuenta.
    """

    model_config = ConfigDict(extra="forbid")

    since: AwareDatetime = Field(description="Desde (incluido), ISO 8601 con zona")
    until: AwareDatetime = Field(description="Hasta (excluido), como tarde hoy a las 00:00 UTC")
    dry_run: bool = True
    confirm_count: int | None = Field(default=None, ge=0, description="Entradas que mostró la vista previa")


class AuditPurgeOut(BaseModel):
    """Entradas del rango (``matched``) y las borradas (``deleted``: 0 en la vista previa)."""

    matched: int
    deleted: int


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
    ignore_patterns: list[str] = Field(
        default_factory=list, description="Patrones de nombre que no escanea ningún proyecto (ubicaciones de origen)"
    )


class LocationOut(LocationPublic):
    """Ubicación vista por un administrador."""

    container_path: str
    latency_ms: float | None
    free_bytes: int | None
    writable: bool | None
    created_at: datetime
    updated_at: datetime


# Límites amplios aquí (422); los del dominio (30 patrones de hasta 64 caracteres, sin separadores) dan 400.
IgnorePatterns = Annotated[
    list[Annotated[str, Field(max_length=1024)]] | None,
    Field(
        max_length=200,
        description="Patrones fnmatch de nombre (sin «/» ni «\\», sin mayúsculas) que no se escanean; solo origen",
    ),
]


class LocationCreate(BaseModel):
    """Alta de ubicación. ``path`` es relativa a ``DOW_LOCATIONS_ROOT`` (``/mnt``) y no se puede cambiar después."""

    name: LocationName
    path: RelativePath
    display_path: DisplayPath | None = None
    kind: LocationKind = "local"
    usage: LocationUsage
    access: LocationAccess = "ro"
    ignore_patterns: IgnorePatterns = None


class LocationUpdate(BaseModel):
    """Edición parcial de ubicación (la carpeta del contenedor no se puede cambiar)."""

    model_config = ConfigDict(extra="forbid")

    name: LocationName | None = None
    display_path: DisplayPath | None = None
    kind: LocationKind | None = None
    usage: LocationUsage | None = None
    access: LocationAccess | None = None
    tenant_id: int | None = Field(default=None, description="Pasarla a otro tenant (si ningún proyecto la usa)")
    ignore_patterns: IgnorePatterns = None


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
    group: Literal["security", "locations", "storage", "ai"] = Field(
        description="Sección de la administración: «Ajustes» (security, locations, storage) o «IA › Parámetros» (ai)."
    )


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
    capture_owner: bool = Field(
        default=False, description="Los escaneos guardan la cuenta propietaria de cada fichero (1.5.0)"
    )
    ai_redact_credentials: bool = Field(
        default=True,
        description="Redactar credenciales de lo que sale hacia la IA y del sitio publicado (D7, W4; por defecto sí)",
    )
    created_at: datetime
    updated_at: datetime
    last_run: RunBrief | None = None
    active_run: bool = False


class ProjectAiSettingsIn(BaseModel):
    """Ajustes de IA del proyecto (W4): propietario o editor, con el destino de lectura y escritura."""

    model_config = ConfigDict(extra="forbid")

    ai_redact_credentials: bool = Field(
        description=(
            "Redactar credenciales (contraseñas, tokens, claves) del texto que se envía a la IA y del sitio publicado. "
            "Desactivarlo envía las credenciales tal cual a la IA"
        )
    )


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
    """Edición parcial: renombrar (solo en la BD), descripción, carpetas de origen y si se guarda el propietario."""

    model_config = ConfigDict(extra="forbid")

    name: ProjectName | None = None
    description: Annotated[str, Field(max_length=1024)] | None = None
    source_subpaths: list[RelativePath] | None = Field(default=None, min_length=1, max_length=20)
    capture_owner: bool | None = Field(
        default=None,
        description=(
            "Guardar la cuenta propietaria de cada fichero desde el siguiente escaneo (dato personal; desactivarlo la "
            "borra de la caché en el siguiente escaneo)"
        ),
    )


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


class ScanExclusionOut(BaseModel):
    """Subcarpeta excluida del escaneo (relativa a la ubicación de origen) y si existe ahora (``None``: no se sabe)."""

    subpath: str
    exists: bool | None


class ScannedFolderOut(_Out):
    """Carpeta de origen del proyecto con su estado en los escaneos (ruta relativa a la ubicación de origen)."""

    subpath: str
    used: bool
    added_at: datetime
    last_scanned_at: datetime | None
    last_run_id: str | None
    available: bool
    excluded: list[ScanExclusionOut] = Field(default_factory=list)


class ScanExclusionsUpdate(BaseModel):
    """Subcarpetas excluidas de una carpeta guardada (sustituye a las anteriores), relativas a la ubicación de origen.

    Hasta 50 (más da 400); las redundantes se colapsan y las que ya no existen se conservan.
    """

    model_config = ConfigDict(extra="forbid")

    excluded: list[Annotated[str, Field(max_length=4096)]] = Field(max_length=500)


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
    mime_type: str | None = Field(default=None, description="Tipo MIME según la extensión (1.5.0)")
    created_at: datetime | None = Field(
        default=None, description="Creación del fichero (1.5.0); nula si el servidor no la da (Linux) o sin escanear"
    )
    file_permissions: str | None = Field(default=None, description="Permisos POSIX en octal (1.5.0); nulos en Windows")
    owner_name: str | None = Field(
        default=None,
        description="Cuenta propietaria (1.5.0): solo si el proyecto la guarda y quien pregunta es owner o admin",
    )


class DocumentPage(BaseModel):
    """Página de documentos del proyecto."""

    items: list[DocumentOut]
    total: int


class MimeTypeOut(BaseModel):
    """Un tipo MIME de los documentos del proyecto y cuántos hay (doc_organize 1.6.0, G43)."""

    mime_type: str
    count: int


class MimeTypeList(BaseModel):
    """Tipos MIME presentes, de más a menos documentos, para el filtro de la lista (1.6.0)."""

    items: list[MimeTypeOut]


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


class TaxonomyAxisSummaryOut(BaseModel):
    """Un eje de una plantilla o manifiesto (doc_organize 2.0): clave, nombre, si organiza carpetas y nº de valores."""

    key: str
    name: str
    organizes: Literal["folder", "subfolder"] | None
    multiple: bool
    values: int


class FrontMatterReportOut(BaseModel):
    """Lo que doc_organize leerá del front matter (``inspect_taxonomy_front_matter``), para avisar al guardar.

    ``implicit_axes``: ejes leídos del formato implícito de 1.x (conviene declararlos en ``axes:``).
    ``ignored_keys``: claves de nivel superior que no se usan al clasificar. ``legacy_format``: el texto es de 1.x.
    """

    axes: list[TaxonomyAxisSummaryOut] = []
    implicit_axes: list[str] = []
    ignored_keys: list[str] = []
    legacy_format: bool = False


class TaxonomyTemplateDetail(TaxonomyTemplateOut):
    """Plantilla con su Markdown, su catálogo y lo que avisa su front matter (W3)."""

    markdown: str
    domains: list[CatalogEntryOut]
    material_types: list[CatalogEntryOut]
    front_matter: FrontMatterReportOut = FrontMatterReportOut()


class TaxonomyMarkdownIn(BaseModel):
    """Markdown de una plantilla o manifiesto: front matter YAML (``domains``, ``material_types``) y prosa."""

    model_config = ConfigDict(extra="forbid")

    markdown: str = Field(min_length=1, max_length=262_144)


class TaxonomyManifestOut(BaseModel):
    """``taxonomy_manifest.md`` del proyecto: ``markdown`` nulo si no existe; ``error`` si no es válido.

    ``etag`` se envía en ``If-Match`` al guardar, borrar o restaurar (``"none"`` si no hay manifiesto).
    ``last_changed_at`` es la fecha de la versión más reciente (último cambio hecho desde la app), o nula.
    """

    markdown: str | None
    error: str | None = None
    domains: list[CatalogEntryOut] = []
    material_types: list[CatalogEntryOut] = []
    front_matter: FrontMatterReportOut = FrontMatterReportOut()
    etag: str
    last_changed_at: datetime | None = None


class ProfileSectionsOut(BaseModel):
    """Secciones de un perfil de proyecto (doc_organize 2.0, G2): lo que se envía al modelo al clasificar."""

    context: str | None = None
    tie_breakers: str | None = None
    glossary: str | None = None
    examples: list[str] = []


class ProjectProfileOut(BaseModel):
    """``.doc_organize/profile.md`` del proyecto (D11: se añade al perfil de la plantilla o el manifiesto).

    ``markdown`` nulo si no existe; ``sections`` lo que doc_organize reconoce (nulo si ninguna sección). ``etag`` se
    envía en ``If-Match`` al guardar o borrar (``"none"`` si no hay perfil).
    """

    markdown: str | None
    sections: ProfileSectionsOut | None = None
    etag: str


class ProjectProfileIn(BaseModel):
    """Perfil propio del proyecto: Markdown con las secciones ``## Contexto del proyecto``, ``## Reglas de
    desempate``, ``## Glosario`` y ``## Ejemplos``."""

    model_config = ConfigDict(extra="forbid")

    markdown: str = Field(min_length=1, max_length=32_768)


class PromptPreviewIn(BaseModel):
    """Vista previa del prompt de clasificación: con la plantilla ``template_name`` o con el manifiesto del proyecto, y
    con ``profile_markdown`` (un borrador sin guardar) o, si es nulo, el perfil guardado."""

    model_config = ConfigDict(extra="forbid")

    catalog: Literal["template", "manifest"] = "manifest"
    template_name: str | None = Field(default=None, max_length=64)
    profile_markdown: str | None = Field(default=None, max_length=32_768)


class TemplatePromptPreviewIn(BaseModel):
    """Vista previa del prompt de una plantilla (su perfil, sin el de ningún proyecto)."""

    model_config = ConfigDict(extra="forbid")

    markdown: str = Field(min_length=1, max_length=262_144)


class PromptMessageOut(BaseModel):
    role: str
    content: str


class PromptPreviewOut(BaseModel):
    """Lo que recibiría el modelo al clasificar (sin llamarlo): los mensajes y el perfil de la plantilla, el del
    proyecto y el compuesto que va en el prompt."""

    messages: list[PromptMessageOut]
    template_profile: ProfileSectionsOut | None = None
    project_profile: ProfileSectionsOut | None = None
    profile: ProfileSectionsOut | None = None


class ManifestVersionOut(BaseModel):
    """Versión anterior del manifiesto (sin el texto): lo que había antes de ``action``.

    ``empty``: no había manifiesto. ``valid``: era un manifiesto válido (se puede restaurar).
    """

    id: int
    created_at: datetime
    created_by: str | None
    action: Literal["save", "delete", "restore", "history_clear"]
    empty: bool
    valid: bool
    domains: int | None
    material_types: int | None


class ManifestVersionList(BaseModel):
    items: list[ManifestVersionOut]
    #: Cuántas se conservan por proyecto.
    limit: int


class ManifestVersionDetail(ManifestVersionOut):
    markdown: str | None


class ContextDomainOut(BaseModel):
    slug: str
    name: str
    description: str | None
    status: str
    documents: int


class ContextAxisValueOut(BaseModel):
    """Un valor de un eje del contexto y cuántos documentos lo tienen."""

    slug: str
    name: str
    documents: int


class ContextAxisOut(BaseModel):
    """Un eje del contexto (``Context.taxonomy_axes``, doc_organize 2.0) con sus valores y recuentos."""

    key: str
    name: str
    description: str | None = None
    multiple: bool = False
    organizes: Literal["folder", "subfolder"] | None = None
    values: list[ContextAxisValueOut]


class PromptProvenanceOut(BaseModel):
    """Con qué prompt y qué modelo se hizo una tarea de IA en la construcción (``Context.ai_provenance``)."""

    task: str
    prompt_id: str
    version: str
    source: str = Field(description="builtin (empaquetado) o project (prompt propio del proyecto)")
    model: str


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
    #: Trazabilidad (1.5.0): versión de doc_organize y modelos de IA usados; nulos en contextos anteriores.
    built_with_version: str | None = None
    ai_classification_model: str | None = None
    ai_enrichment_model: str | None = None
    domains: list[ContextDomainOut]
    #: W3 (doc_organize 2.0): ejes con recuentos por valor y procedencia de la IA; vacíos en contextos anteriores.
    taxonomy_axes: list[ContextAxisOut] = []
    ai_provenance: list[PromptProvenanceOut] = []
    built_by_run_id: str | None
    built_at: datetime


class AxisValueOut(_Out):
    """Un valor de un eje de un documento: quién lo asignó (``rules``, ``semantic``, ``ai`` o ``human``) y, si lo dio
    la IA, la cita literal y si se encontró en el texto enviado (D10: sin verificar, confianza bajo el umbral)."""

    slug: str
    name: str
    confidence: float | None = None
    classified_by: Literal["rules", "semantic", "ai", "human"] | None = None
    evidence: str | None = None
    evidence_verified: bool | None = None


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
    # 1.5.0: propiedades declaradas en el documento (o de la IA si faltan: ``ai_filled``) e idioma detectado.
    author: str | None = None
    description: str | None = None
    keywords: list[str] = []
    language: str | None = None
    ai_filled: list[str] = []
    # 1.5.0: cómo se clasificó. Reglas y su confianza, propuesta de la IA (puede diferir del dominio) y justificación.
    rules_domain: str | None = None
    rules_confidence: float | None = None
    ai_domain: str | None = None
    ai_confidence: float | None = None
    ai_reasoning: str | None = None
    material_type_confidence: float | None = None
    # 1.6.0 (G42): por qué no se clasificó; los sin clasificar traen también sus propiedades y lo que propusieron las
    # reglas por debajo del umbral (``rules_domain``, ``rules_confidence``). Nulo en contextos anteriores.
    unclassified_reason: Literal["incomplete_artifacts", "below_threshold"] | None = None
    #: W3 (doc_organize 2.0): valores de cada eje, por clave de eje; vacío en contextos anteriores a 2.0.
    axes: dict[str, list[AxisValueOut]] = {}


class ContextChangeOut(BaseModel):
    """Documento que entró, salió o cambió de dominio o tipo de material en una construcción (1.5.0)."""

    path: str = Field(description="Original relativo a la carpeta de origen (``<carpeta>/<ruta>``)")
    #: doc_organize 2.0: ``superseded`` (versión antigua fuera del contexto) y ``excluded`` (lo sacó una persona).
    change: Literal["added", "removed", "reclassified", "superseded", "excluded"]
    previous_domain: str | None
    domain: str | None
    previous_material_type: str | None
    material_type: str | None
    classified_by: str | None


class ContextBuildOut(BaseModel):
    """Una construcción del historial del contexto (1.5.0)."""

    built_at: str
    previous_built_at: str | None
    built_with_version: str | None
    taxonomy_manifest_used: bool
    ai_classification_model: str | None
    ai_enrichment_model: str | None
    classified: int
    unclassified: int
    changes_total: int = Field(description="Cambios de la construcción; en ``changes`` van como mucho los primeros")
    changes: list[ContextChangeOut]


class ContextHistoryOut(BaseModel):
    """Últimas construcciones del contexto, las más recientes primero (1.5.0). Se conserva al borrar el contexto."""

    items: list[ContextBuildOut]
    total: int
    error: Literal["history_too_large"] | None = Field(
        default=None, description="No se leyó: el historial es demasiado grande; usa la exportación a Excel"
    )


class ContextDocumentPage(BaseModel):
    items: list[ContextDocumentOut]
    total: int


class SiteSessionOut(BaseModel):
    """URL del sitio aislado (con su token) y su caducidad."""

    url: str
    expires_at: datetime


# --- ai (Fase 8) -------------------------------------------------------------------------------------------------

#: doc_organize 2.0 (W2): una familia ``litellm`` para todas las tareas de IA (migración ``0016``) y las dos de uso.
AiFamilyKey = Literal["litellm", "litellm_usage", "github_copilot_usage"]
AiTaskKey = Literal["classify", "enrich", "taxonomy_design", "agent", "embed"]


class AiFieldOut(BaseModel):
    """Campo de una familia de IA. ``value`` solo en los no secretos; ``hint`` («…ab12» o «***») solo en los secretos."""

    name: str
    env_var: str | None = Field(description="Variable de entorno equivalente; null si el campo no tiene")
    secret: bool
    required: bool
    source: Literal["db", "env", "none"]
    value: str | None
    hint: str | None
    undecryptable: bool = Field(description="Hay un valor guardado que no se descifra con las claves actuales")
    task: AiTaskKey | None = Field(
        default=None, description="Tarea del campo en la familia litellm (modelo, clave o presupuesto); null = de todas"
    )


class AiLegacyVariableOut(BaseModel):
    """Variable de entorno de doc_organize 1.x que sigue definida y ya no se lee (D15), con la que la sustituye."""

    name: str
    replacement: str


class AiFamilyOut(BaseModel):
    key: AiFamilyKey
    configured: bool = Field(description="Tiene todos sus campos obligatorios")
    fields: list[AiFieldOut]


class AiSettingsOut(BaseModel):
    """Configuración de IA de la instancia, sin ningún secreto."""

    encryption_configured: bool
    families: list[AiFamilyOut]
    legacy_variables: list[AiLegacyVariableOut] = Field(
        default_factory=list,
        description="Variables de entorno de doc_organize 1.x definidas que ya no se leen (solo nombres, D15/U17)",
    )


class AiFamilyUpdate(BaseModel):
    """Campos que cambian: ausente = no se toca; ``null`` o ``""`` = borrar el valor guardado (vuelve al entorno)."""

    model_config = ConfigDict(extra="forbid")

    fields: dict[Annotated[str, Field(max_length=32)], Annotated[str, Field(max_length=4096)] | None] = Field(
        max_length=16
    )


class AiTestIn(BaseModel):
    """«Probar conexión»: valores del formulario que sustituyen a los efectivos (ausente = el efectivo; ``null`` o ``""``
    = sin valor). No se guarda nada."""

    model_config = ConfigDict(extra="forbid")

    fields: dict[Annotated[str, Field(max_length=32)], Annotated[str, Field(max_length=4096)] | None] = Field(
        default_factory=dict, max_length=16
    )
    model_check: bool = Field(
        default=False,
        description="Enviar también una petición mínima al modelo (gasta unos pocos tokens; solo familias con modelo)",
    )
    task: AiTaskKey = Field(default="classify", description="Tarea cuyo modelo se prueba (familia litellm)")


class AiTestOut(BaseModel):
    """Resultado de «Probar conexión»: solo un código, nunca el cuerpo de lo que respondió el servidor."""

    ok: bool
    error: Literal["ai_auth", "ai_connection", "ai_error", "ai_model"] | None = Field(
        description="Credencial rechazada, sin conexión o timeout, otro error, o el modelo no respondió"
    )
    model_access: Literal["ok", "denied", "unknown"] = Field(
        description="Si la clave de LiteLLM tiene acceso al modelo según /key/info (unknown si no lo dice)"
    )
    model_checked: bool = Field(description="Si se envió la petición al modelo")
    task: AiTaskKey | None = Field(default=None, description="Tarea cuyo modelo se probó (familia litellm)")
    response_format: Literal["json_schema", "json_object"] | None = Field(
        default=None, description="Formato con el que respondió el modelo: json_schema si admite la salida estricta"
    )
    elapsed_ms: int
    tested_at: AwareDatetime


class AiStatusOut(BaseModel):
    """Qué familias y qué tareas de IA están configuradas (para cualquier usuario, sin valores)."""

    families: dict[str, bool]
    tasks: dict[str, bool] = Field(
        default_factory=dict, description="Tarea de IA (doc_organize 2.0) → si se puede usar"
    )


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
