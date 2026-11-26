"""Documentos, visor y búsqueda (Fase 5)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.api.v1.schemas._common import _Out


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
