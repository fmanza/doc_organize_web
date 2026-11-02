"""Cifrado de las credenciales de IA con MultiFernet (ADR-004, Fase 8).

``DOW_FERNET_KEYS`` es una lista separada por comas: la primera cifra y todas descifran, así que para rotar se
antepone una clave nueva y se ejecuta ``python -m app.cli rotate-secrets``. Ningún mensaje de error lleva el valor.
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.core.config import Settings


class EncryptionNotConfiguredError(Exception):
    """No hay ``DOW_FERNET_KEYS`` (o ninguna clave es válida): no se puede guardar ni leer un secreto."""


class UndecryptableError(Exception):
    """El token no se descifra con ninguna de las claves (clave retirada antes de volver a cifrar)."""


def cipher(settings: Settings) -> MultiFernet:
    """MultiFernet con las claves de ``settings.fernet_keys``.

    Raises:
        EncryptionNotConfiguredError: Sin claves o con alguna que no es una clave Fernet.
    """
    if settings.fernet_keys is None:
        raise EncryptionNotConfiguredError()
    raw = [key.strip() for key in settings.fernet_keys.get_secret_value().split(",") if key.strip()]
    if not raw:
        raise EncryptionNotConfiguredError()
    try:
        return MultiFernet([Fernet(key.encode("ascii")) for key in raw])
    except (ValueError, UnicodeEncodeError):
        raise EncryptionNotConfiguredError() from None


def is_configured(settings: Settings) -> bool:
    """Si hay claves Fernet válidas."""
    try:
        cipher(settings)
    except EncryptionNotConfiguredError:
        return False
    return True


def encrypt(settings: Settings, value: str) -> str:
    """Token Fernet de ``value`` con la primera clave."""
    return cipher(settings).encrypt(value.encode("utf-8")).decode("ascii")


def decrypt(settings: Settings, token: str) -> str:
    """Valor de ``token``.

    Raises:
        EncryptionNotConfiguredError: Sin claves.
        UndecryptableError: Ninguna clave lo descifra.
    """
    try:
        return cipher(settings).decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeError):
        raise UndecryptableError() from None


def rotate(settings: Settings, token: str) -> str:
    """``token`` vuelto a cifrar con la primera clave (``MultiFernet.rotate``).

    Raises:
        UndecryptableError: Ninguna clave lo descifra.
    """
    try:
        return cipher(settings).rotate(token.encode("ascii")).decode("ascii")
    except (InvalidToken, UnicodeError):
        raise UndecryptableError() from None
