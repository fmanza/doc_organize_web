"""Errores de dominio del escaneo, con ``code`` estable para el cliente."""

from __future__ import annotations

from app.core.errors import AppError


class OptionUnavailableError(AppError):
    """La instancia no puede atender una opción del escaneo (sin GPU, sin audio/vídeo o sin el modelo de visión)."""

    status = 422
    title = "Opción de escaneo no disponible"
    code = "option_unavailable"


class FolderNotSavedError(AppError):
    """El escaneo pide una carpeta que no es una carpeta de origen del proyecto."""

    status = 422
    title = "Carpeta no guardada en el proyecto"
    code = "folder_not_saved"


class ForceRequiresAllFoldersError(AppError):
    """«Forzar reconversión» vacía toda la caché: con un subconjunto borraría las salidas de las demás carpetas."""

    status = 422
    title = "Forzar reconversión exige todas las carpetas"
    code = "force_requires_all_folders"


class ScannedFolderNotFoundError(AppError):
    """La carpeta no está entre las carpetas de origen del proyecto."""

    status = 404
    title = "Carpeta no encontrada en el proyecto"


class LastFolderError(AppError):
    """Un proyecto necesita al menos una carpeta de origen."""

    status = 409
    title = "Es la única carpeta de origen"
    code = "last_folder"
