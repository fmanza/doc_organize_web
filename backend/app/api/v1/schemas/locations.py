"""Ubicaciones origen/destino y exploración de carpetas."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.api.v1.schemas._common import _Out

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


class LocationProjectRef(BaseModel):
    """Proyecto activo que usa una ubicación."""

    id: int
    name: str


class LocationUsageOut(BaseModel):
    """Proyectos que usan una ubicación (2.1.1): mientras haya alguno, no se puede borrar."""

    active_projects: list[LocationProjectRef] = Field(description="Proyectos activos que la usan, por nombre")
    can_delete: bool = Field(description="Ningún proyecto activo la usa")


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
