"""Errores de dominio de proyectos, convertidos en *problem details* por ``app.core.errors``.

Como en las ubicaciones, ningún mensaje incluye rutas del contenedor: solo nombres y rutas relativas.
"""

from __future__ import annotations

from app.core.errors import AppError


class ProjectNotFoundError(AppError):
    """Proyecto inexistente, borrado o del que el usuario no es miembro (mismo 404: sin revelar que existe)."""

    status = 404
    title = "Proyecto no encontrado"


class ProjectForbiddenError(AppError):
    """El usuario es miembro, pero su rol no permite la acción."""

    status = 403
    title = "Tu rol en el proyecto no permite esta acción"


class InvalidProjectError(AppError):
    """Datos del proyecto no válidos: ubicaciones de uso o acceso incorrecto, rutas solapadas o nombre de carpeta."""

    title = "Proyecto no válido"


class ProjectConflictError(AppError):
    """Ya existe un proyecto con ese nombre o la carpeta de salidas no está libre."""

    status = 409
    title = "Conflicto con otro proyecto"


class FolderNotEmptyError(AppError):
    """La carpeta de salidas elegida ya tiene contenido (el proyecto debe ser dueño de su carpeta)."""

    status = 409
    title = "La carpeta no está vacía"
    code = "folder_not_empty"


class MemberNotFoundError(AppError):
    """El usuario no es miembro del proyecto."""

    status = 404
    title = "Miembro no encontrado"


class MemberConflictError(AppError):
    """Alta de un miembro que ya lo es, o cambio que dejaría el proyecto sin propietario."""

    status = 409
    title = "Conflicto con los miembros del proyecto"
