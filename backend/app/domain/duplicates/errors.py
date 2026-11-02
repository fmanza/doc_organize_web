"""Errores de dominio de duplicados (Fase 6), con ``code`` estable para el cliente."""

from __future__ import annotations

from app.core.errors import AppError


class DuplicatePreviewRequiredError(AppError):
    """La vista previa de duplicados no existe, no es de este proyecto, no terminó bien o ha caducado."""

    status = 422
    title = "Vista previa de duplicados no válida"
    code = "duplicates_preview_required"


class GroupNotInPreviewError(AppError):
    """Un grupo enviado no está en la vista previa, o el documento a conservar no es de ese grupo."""

    status = 422
    title = "Grupo no válido"
    code = "group_not_in_preview"


class SourceReadOnlyError(AppError):
    """Mover duplicados saca ficheros del origen: no se puede con una ubicación de solo lectura."""

    status = 422
    title = "La ubicación de origen es de solo lectura"
    code = "location_read_only"
