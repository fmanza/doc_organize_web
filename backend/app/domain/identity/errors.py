"""Errores de dominio de identidad, convertidos en *problem details* por ``app.core.errors``."""

from __future__ import annotations

from app.core.errors import AppError


class InvalidCredentialsError(AppError):
    """Usuario inexistente, desactivado, bloqueado o contraseña incorrecta: mismo mensaje para no enumerar."""

    status = 401
    title = "Credenciales no válidas"

    def __init__(self) -> None:
        super().__init__("Usuario o contraseña incorrectos, o cuenta bloqueada temporalmente.")


class PasswordPolicyError(AppError):
    """La contraseña nueva no cumple la política."""

    title = "Contraseña no válida"


class WrongCurrentPasswordError(AppError):
    """La contraseña actual indicada al cambiarla no es correcta."""

    title = "Contraseña actual incorrecta"


class UserNotFoundError(AppError):
    """Usuario inexistente."""

    status = 404
    title = "Usuario no encontrado"


class SessionNotFoundError(AppError):
    """Sesión inexistente o ya caducada."""

    status = 404
    title = "Sesión no encontrada"


class UsernameTakenError(AppError):
    """Nombre de usuario ya registrado."""

    status = 409
    title = "El usuario ya existe"


class LastAdminError(AppError):
    """La operación dejaría el sistema sin administradores activos."""

    status = 409
    title = "Debe quedar al menos un administrador activo"


class SelfModificationError(AppError):
    """Un administrador no puede desactivarse ni quitarse el rol a sí mismo."""

    status = 409
    title = "No puedes desactivarte ni quitarte el rol de administrador"
