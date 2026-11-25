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
    code = "last_admin"


class UserDeletionConflictError(AppError):
    """El usuario no se puede borrar sin dejar algo huérfano (ADR-016): ``reasons`` dice por qué.

    Las extensiones del *problem details* repiten la comprobación previa (``deletion-check``): solo ids, nombres y
    recuentos, nunca rutas ni secretos.
    """

    status = 409
    title = "No se puede borrar el usuario"
    code = "user_has_dependencies"

    def __init__(self, check: dict[str, object]) -> None:
        super().__init__("Resuelve antes lo que indica la comprobación.")
        self.check = check

    def extensions(self) -> dict[str, object]:
        return dict(self.check)


class SelfModificationError(AppError):
    """Un administrador no puede desactivarse ni quitarse el rol a sí mismo."""

    status = 409
    title = "No puedes desactivarte ni quitarte el rol de administrador"
