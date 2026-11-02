"""Errores de dominio de la IA (Fase 8), con ``code`` estable para el cliente. Ninguno lleva un valor secreto."""

from __future__ import annotations

from app.core.errors import AppError


class AiFamilyNotFoundError(AppError):
    """No es una de las 5 familias de configuración de IA."""

    status = 404
    title = "Familia de IA desconocida"
    code = "ai_family_not_found"


class InvalidAiSettingError(AppError):
    """Campo ajeno a la familia o valor no válido (p. ej. una ``base_url`` sin esquema http/https)."""

    status = 422
    title = "Configuración de IA no válida"
    code = "ai_setting_invalid"


class EncryptionNotConfiguredError(AppError):
    """Se intenta guardar un secreto sin ``DOW_FERNET_KEYS``."""

    status = 409
    title = "Cifrado no configurado"
    code = "encryption_not_configured"


class AiNotConfiguredError(AppError):
    """La operación usa una familia de IA a la que le falta algún campo obligatorio."""

    status = 422
    title = "IA no configurada"
    code = "ai_not_configured"
