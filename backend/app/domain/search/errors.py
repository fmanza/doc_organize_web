"""Errores de dominio de la búsqueda de texto completo."""

from __future__ import annotations

from app.core.errors import AppError


class SearchTooBroadError(AppError):
    """La consulta tarda demasiado (palabras muy comunes o muy cortas): hay que concretar más."""

    status = 422
    title = "Búsqueda demasiado amplia"
    code = "search_too_broad"
