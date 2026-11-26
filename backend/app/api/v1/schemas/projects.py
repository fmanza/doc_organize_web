"""Proyectos, miembros, carpetas y exclusiones."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.api.v1.schemas._common import _Out
from app.api.v1.schemas.locations import LocationAccess, LocationStatus, RelativePath

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
    "export_site",
    "export_ai_bundle",
    "search_index",
    "dedup_preview",
    "dedup_apply",
    "context_build",
    "context_delete",
    "taxonomy_draft",
    "context_evaluate",
    "context_dry_run",
    "taxonomy_agent",
    "taxonomy_check",
    "context_review_agent",
    "context_audit",
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
    context_versions: Literal["all", "mark", "current_only"] = "mark"
    context_versions_across_extensions: bool = False
    context_semantic: bool = False
    context_semantic_threshold: float = 0.75
    created_at: datetime
    updated_at: datetime
    last_run: RunBrief | None = None
    active_run: bool = False


class ProjectAiSettingsIn(BaseModel):
    """Ajustes de IA y del contexto del proyecto (W4, W6): propietario o editor, con el destino de lectura y escritura.
    Ausente = no se toca; se aplican desde la siguiente construcción."""

    model_config = ConfigDict(extra="forbid")

    ai_redact_credentials: bool | None = Field(
        default=None,
        description=(
            "Redactar credenciales (contraseñas, tokens, claves) del texto que se envía a la IA y del sitio publicado. "
            "Desactivarlo envía las credenciales tal cual a la IA"
        ),
    )
    context_versions: Literal["all", "mark", "current_only"] | None = Field(
        default=None,
        description=(
            "Versiones de un mismo documento (F5): all (todas, como 1.x), mark (marcar la vigente, por defecto en la "
            "web) o current_only (solo la vigente entra en el contexto)"
        ),
    )
    context_versions_across_extensions: bool | None = Field(
        default=None,
        description=(
            "Agrupar versiones aunque cambie el formato (Manual_v2.docx con Manual_v3.pdf; 2.5.0). Desactivado por "
            "defecto: dos ficheros con el mismo nombre en otro formato pueden no ser el mismo documento"
        ),
    )
    context_semantic: bool | None = Field(
        default=None, description="Sub-fase semántica con embeddings antes de la IA (G4, opt-in; tarea embed)"
    )
    context_semantic_threshold: float | None = Field(
        default=None, ge=0, le=1, description="Similitud mínima para asignar un valor por semántica"
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
