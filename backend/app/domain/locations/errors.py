"""Errores de dominio de ubicaciones, convertidos en *problem details* por ``app.core.errors``.

Ninguno incluye la ruta del contenedor en el mensaje: el usuario solo ve el nombre de la ubicación y su ruta relativa.
"""

from __future__ import annotations

from app.core.errors import AppError


class LocationNotFoundError(AppError):
    """Ubicación inexistente o no visible para el usuario."""

    status = 404
    title = "Ubicación no encontrada"


class FolderNotFoundError(AppError):
    """Carpeta inexistente **o fuera de la ubicación**: mismo error para no revelar qué existe fuera (ADR-007)."""

    status = 404
    title = "Carpeta no encontrada"


class InvalidRelativePathError(AppError):
    """La ruta no es relativa a la ubicación (absoluta, UNC, unidad, ``\\``, ``..`` o bytes nulos)."""

    title = "Ruta no válida"


class LocationUnavailableError(AppError):
    """La ubicación no responde (montaje caído, colgado o sin permisos de lectura)."""

    status = 503
    title = "Ubicación no disponible"


class InvalidLocationPathError(AppError):
    """La carpeta propuesta para una ubicación no es válida (fuera de la raíz, inexistente o solapada)."""

    title = "Carpeta de la ubicación no válida"


class LocationConflictError(AppError):
    """Ya existe una ubicación con ese nombre o esa carpeta."""

    status = 409
    title = "La ubicación ya existe"
