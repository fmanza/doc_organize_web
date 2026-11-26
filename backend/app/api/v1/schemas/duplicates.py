"""Duplicados (Fase 6)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.api.v1.schemas.projects import RunBrief


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
    reason: Literal["exact_duplicate", "version_conflict", "fuzzy_name_match", "same_content", "semantic_content_match"]
    members: list[DuplicateMemberOut]
    similarity: float | None = Field(
        default=None, description="Por contenido (2.2): similitud semántica, la menor entre los miembros (0-1)"
    )
    lexical_similarity: float | None = Field(
        default=None,
        description="Por contenido (2.2): similitud de texto (0-1); baja con la semántica alta = reescrito",
    )
    contained: bool = Field(default=False, description="Por contenido (2.2): un miembro está contenido en otro")


class DuplicateGroupPage(BaseModel):
    """Página de grupos de una vista previa de duplicados."""

    run: RunBrief
    items: list[DuplicateGroupOut]
    total: int


class DuplicatesLastOut(BaseModel):
    """Última búsqueda de duplicados y última aplicación real del proyecto (``None`` si no hay)."""

    preview: RunBrief | None
    apply: RunBrief | None
    exclusions_changed: bool = Field(
        default=False, description="Las exclusiones del proyecto cambiaron después de la última búsqueda (2.7)"
    )
