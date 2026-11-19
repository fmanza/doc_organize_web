"""Errores de dominio de la IA (Fase 8), con ``code`` estable para el cliente. Ninguno lleva un valor secreto."""

from __future__ import annotations

from app.core.errors import AppError


class AiFamilyNotFoundError(AppError):
    """No es una de las 6 familias de configuración de IA."""

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


class SecretRequiredError(AppError):
    """Se prueba otra ``base_url`` sin escribir la clave: la guardada nunca se manda a un servidor distinto."""

    status = 422
    title = "Escribe la clave para probar con otra URL"
    code = "secret_required"


class AiTestTooSoonError(AppError):
    """Otra prueba de la misma familia hace menos de ``MIN_TEST_INTERVAL_SECONDS``."""

    status = 429
    title = "Espera unos segundos antes de volver a probar"
    code = "ai_test_too_soon"


class DiagnosticsTooSoonError(AppError):
    """Hay un diagnóstico en marcha o el último fue hace muy poco."""

    status = 429
    title = "Espera antes de volver a diagnosticar"
    code = "diagnostics_too_soon"


class DiagnosticsFailedError(AppError):
    """El diagnóstico no terminó (tiempo agotado o fallo del subproceso); sin detalles."""

    status = 503
    title = "No se pudo completar el diagnóstico"
    code = "diagnostics_failed"
