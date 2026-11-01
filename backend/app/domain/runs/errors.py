"""Errores de dominio de ejecuciones, con ``code`` estable para el cliente."""

from __future__ import annotations

from app.core.errors import AppError


class RunNotFoundError(AppError):
    """Run inexistente o de un proyecto que el usuario no ve (mismo 404)."""

    status = 404
    title = "Ejecución no encontrada"


class ArtifactNotFoundError(AppError):
    """Artefacto inexistente o de otro run."""

    status = 404
    title = "Artefacto no encontrado"


class ArtifactGoneError(AppError):
    """El artefacto existió, pero la retención ya borró la carpeta del run."""

    status = 410
    title = "Artefacto caducado"
    code = "artifact_purged"


class WriteLockedError(AppError):
    """Ya hay una operación de escritura en cola o en marcha en el proyecto."""

    status = 409
    title = "Hay otra operación de escritura en curso"
    code = "write_locked"


class PreviewRequiredError(AppError):
    """La operación destructiva exige una vista previa vigente y el nombre del proyecto."""

    status = 409
    title = "Se necesita una vista previa confirmada"
    code = "preview_required"


class QuotaExceededError(AppError):
    """El usuario superó su cuota de artefactos en el workspace."""

    status = 409
    title = "Cuota de espacio superada"
    code = "quota_exceeded"


class RunFinishedError(AppError):
    """El run ya terminó (no se puede cancelar)."""

    status = 409
    title = "La ejecución ya ha terminado"
    code = "run_finished"


class RunNotAllowedError(AppError):
    """El usuario no puede cancelar este run (no lo lanzó y no es propietario del proyecto)."""

    status = 403
    title = "No puedes cancelar esta ejecución"


class TooManyRunsError(AppError):
    """El usuario ya tiene el máximo de runs en cola o en marcha."""

    status = 409
    title = "Demasiadas ejecuciones en curso"
    code = "too_many_runs"
