"""Primitivas criptográficas de sesión y CSRF (ADR-003), sin estado ni dependencias de dominio."""

from __future__ import annotations

import hashlib
import hmac
import secrets

from app.core.config import Settings

SESSION_TOKEN_BYTES = 32  # 256 bits
CSRF_TOKEN_BYTES = 32

# Clave efímera por proceso para development/test sin ``dow_app_secret_key``; en producción ``Settings`` exige la
# clave al arrancar.
_EPHEMERAL_KEY = secrets.token_bytes(32)


def _signing_key(settings: Settings) -> bytes:
    if settings.app_secret_key is None:
        return _EPHEMERAL_KEY
    return settings.app_secret_key.get_secret_value().encode("utf-8")


def new_session_token() -> str:
    """Token de sesión aleatorio de 256 bits (solo viaja en la cookie; en BD se guarda su hash)."""
    return secrets.token_urlsafe(SESSION_TOKEN_BYTES)


def new_csrf_token() -> str:
    """Token CSRF anónimo para el doble envío previo al inicio de sesión."""
    return secrets.token_urlsafe(CSRF_TOKEN_BYTES)


def hash_token(token: str) -> str:
    """SHA-256 hexadecimal del token de sesión (lo único que se persiste)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def session_csrf_token(settings: Settings, session_token: str) -> str:
    """Token CSRF ligado a la sesión: ``HMAC-SHA256(clave, token_de_sesión)``.

    Una cookie CSRF inyectada desde otro origen no sirve sin conocer la clave y el token de sesión.
    """
    return hmac.new(_signing_key(settings), session_token.encode("utf-8"), hashlib.sha256).hexdigest()


def tokens_match(a: str, b: str) -> bool:
    """Comparación en tiempo constante."""
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
