"""Errores de dominio de documentos y salidas convertidas, con ``code`` estable para el cliente."""

from __future__ import annotations

from app.core.errors import AppError


class OutputNotFoundError(AppError):
    """La salida no existe, no es un fichero o queda fuera de ``Conversión/`` (mismo error, no se revela cuál)."""

    status = 404
    title = "Salida no encontrada"
    code = "output_not_found"


class OutputTypeNotAllowedError(AppError):
    """Tipo de fichero que el visor no sirve (SVG, HTML, PDF…): podría ejecutar código en el navegador."""

    status = 415
    title = "Tipo de fichero no permitido en el visor"
    code = "output_type_not_allowed"


class OutputTooLargeError(AppError):
    """La salida supera el tamaño máximo del visor; se obtiene con una exportación."""

    status = 413
    title = "Fichero demasiado grande para el visor"
    code = "output_too_large"


class FolderNotInProjectError(AppError):
    """El filtro de carpeta no es una carpeta de origen del proyecto."""

    status = 422
    title = "Carpeta no guardada en el proyecto"
    code = "folder_not_saved"
