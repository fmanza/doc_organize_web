"""Escaneo y conversión (Fase 4)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.api.v1.schemas._common import _Out
from app.api.v1.schemas.projects import LocationRef, RunBrief


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


class ProjectExclusionPathOut(BaseModel):
    """Carpeta excluida del proyecto, relativa a la ubicación de origen; ``exists`` es ``None`` si no se pudo mirar."""

    path: str
    exists: bool | None


class ProjectExclusionsOut(BaseModel):
    """Exclusiones del proyecto (web 2.7, ADR-017) y lo que se suma a ellas sin poder editarlo aquí.

    Valen en escaneo, duplicados, contexto y exportaciones de la caché, junto con las subcarpetas excluidas de cada
    carpeta guardada.
    """

    excluded: list[ProjectExclusionPathOut]
    ignore_patterns: list[str]
    exclude_system_folders: bool
    system_patterns: list[str] = Field(description="Patrones del preset de carpetas de sistema")
    location_patterns: list[str] = Field(description="Patrones de la ubicación de origen (los fija un admin)")


class ProjectExclusionsUpdate(BaseModel):
    r"""Exclusiones del proyecto (sustituyen a las anteriores).

    ``excluded``: hasta 100 carpetas relativas a la ubicación de origen, dentro de alguna carpeta del proyecto (las
    redundantes se colapsan y las que ya no existen se conservan). ``ignore_patterns``: hasta 30 patrones de nombre
    (``fnmatch``, sin «/» ni «\», como mucho 64 caracteres; no se admiten los que lo excluirían todo, como ``*``).
    """

    model_config = ConfigDict(extra="forbid")

    excluded: list[Annotated[str, Field(max_length=4096)]] = Field(default_factory=list, max_length=500)
    ignore_patterns: list[Annotated[str, Field(max_length=64)]] = Field(default_factory=list, max_length=100)
    exclude_system_folders: bool


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
