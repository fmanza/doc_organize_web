"""Casos de uso de ejecuciones en la API: encolar, consultar, cancelar y artefactos (ADR-002).

La API **nunca ejecuta** una operación: valida, crea la fila ``queued`` y su primer evento, y el worker la reclama.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from pathlib import Path
from typing import Final

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import ACTIVE_RUN_STATUSES, FINISHED_RUN_STATUSES, Artifact, MemberRole, Project, Run, User, utcnow
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction, RequestContext
from app.domain.locations.paths import join_relative, normalize_relative, resolve_within
from app.domain.projects import service as projects
from app.domain.projects.errors import InvalidProjectError, ProjectForbiddenError, ProjectNotFoundError
from app.domain.projects.folders import folder_name_problem, nested
from app.domain.projects.service import ROLE_RANK, ProjectAccess
from app.domain.runs import events
from app.domain.runs.errors import (
    ArtifactNotFoundError,
    PreviewRequiredError,
    QuotaExceededError,
    RunFinishedError,
    RunNotAllowedError,
    RunNotFoundError,
    TooManyRunsError,
    WriteLockedError,
)
from app.domain.runs.operations import (
    OPERATIONS,
    ProjectMoveParams,
    RunParams,
    ScanParams,
    is_write,
    min_role,
    needs_preview,
    preview_matches,
    queue_for,
    stored_params,
)
from app.domain.scan.errors import FolderNotSavedError, ForceRequiresAllFoldersError
from app.domain.scan.options import check_options

#: Vigencia de una vista previa para lanzar la operación real.
PREVIEW_TTL: Final = timedelta(minutes=15)
MB: Final = 1024 * 1024
#: Runs en cola o en marcha por usuario: uno solo no puede acaparar la cola (FIFO) del worker.
MAX_ACTIVE_RUNS_PER_USER: Final = 5


def quota_used_bytes(db: Session, user_id: int) -> int:
    """Bytes de artefactos del usuario que siguen en el workspace."""
    query = (
        select(func.coalesce(func.sum(Artifact.size_bytes), 0))
        .join(Run, Run.id == Artifact.run_id)
        .where(Artifact.created_by == user_id, Run.workspace_purged_at.is_(None))
    )
    return int(db.scalar(query) or 0)


def _check_preview(db: Session, project: Project, params: RunParams) -> None:
    preview_id = getattr(params, "preview_run_id", None)
    confirm = getattr(params, "confirm_name", None)
    if not preview_id or confirm is None:
        raise PreviewRequiredError("Lanza primero la vista previa y confirma con el nombre del proyecto.")
    if confirm.strip() != project.name:
        raise PreviewRequiredError("El nombre escrito no coincide con el del proyecto.")
    preview = db.get(Run, preview_id)
    if (
        preview is None
        or preview.project_id != project.id
        or preview.status != "succeeded"
        or not preview_matches(params, preview.params)
    ):
        raise PreviewRequiredError("La vista previa no corresponde a esta operación.")
    if preview.finished_at is None or utcnow() - preview.finished_at > PREVIEW_TTL:
        raise PreviewRequiredError("La vista previa ha caducado: vuelve a lanzarla.")
    since = preview.started_at or preview.created_at
    newer = select(Run.id).where(
        Run.project_id == project.id,
        Run.is_write.is_(True),
        Run.status.in_(ACTIVE_RUN_STATUSES) | (Run.created_at > preview.created_at) | (Run.finished_at >= since),
    )
    # Cambiar las carpetas de origen no es un run, pero cambia lo que haría «forzar»: también invalida.
    if db.scalar(newer.limit(1)) is not None or project.updated_at > preview.created_at:
        raise PreviewRequiredError("El proyecto ha cambiado desde la vista previa: vuelve a lanzarla.")


def _validate_move(db: Session, project: Project, params: ProjectMoveParams, settings: Settings) -> ProjectMoveParams:
    """Comprueba el destino de un movimiento y devuelve los parámetros con la carpeta padre normalizada.

    Raises:
        InvalidProjectError: Destino no válido, igual al actual o dentro de las salidas actuales.
        ProjectConflictError: Otro proyecto usa esa carpeta.
    """
    destination = projects.destination_location(db, params.destination_location_id)
    problem = folder_name_problem(params.new_folder)
    if problem:
        raise InvalidProjectError(problem)
    parent = normalize_relative(params.destination_parent)
    planned = join_relative(parent, params.new_folder)
    if destination.id == project.destination_location_id and nested(planned, project.destination_subpath):
        raise InvalidProjectError("El destino no puede ser la carpeta actual ni estar dentro o por encima de ella.")
    projects.check_destination_free(
        db,
        destination_location_id=destination.id,
        destination_subpath=planned,
        source_location_id=project.source_location_id,
        source_subpaths=project.source_subpaths,
        exclude_project_id=project.id,
    )
    if destination.status == "unavailable":
        raise InvalidProjectError("La ubicación de destino no está disponible.")
    resolved = resolve_within(Path(destination.container_path), parent, timeout=settings.location_probe_timeout_seconds)
    return params.model_copy(update={"destination_parent": resolved.relative})


def _validate_scan(db: Session, project: Project, params: ScanParams, settings: Settings) -> ScanParams:
    """Normaliza las carpetas del escaneo (vacío = todas) y comprueba ``force`` y las opciones.

    Raises:
        FolderNotSavedError: Alguna carpeta no es de origen del proyecto.
        ForceRequiresAllFoldersError: ``force`` con un subconjunto de carpetas.
        OptionUnavailableError: Ningún worker de la cola puede con alguna opción.
    """
    folders = sorted({normalize_relative(f) for f in params.folders}, key=str.casefold)
    unknown = [f or "(raíz)" for f in folders if f not in project.source_subpaths]
    if unknown:
        raise FolderNotSavedError(f"No son carpetas de origen del proyecto: {', '.join(unknown)}.")
    if set(folders) == set(project.source_subpaths):
        folders = []
    if params.force and folders:
        raise ForceRequiresAllFoldersError(
            "«Forzar reconversión» vacía toda la caché: escanea todas las carpetas del proyecto."
        )
    params = params.model_copy(update={"folders": folders})
    check_options(db, settings, params)
    return params


def enqueue(
    db: Session, access: ProjectAccess, params: RunParams, *, settings: Settings, actor: User, ctx: RequestContext
) -> Run:
    """Valida y encola un run del proyecto.

    Raises:
        ProjectForbiddenError: Rol insuficiente para la operación.
        QuotaExceededError: Cuota de artefactos superada.
        PreviewRequiredError: Operación destructiva sin vista previa vigente o sin el nombre confirmado.
        WriteLockedError: Ya hay una escritura en cola o en marcha en el proyecto.
        InvalidProjectError, ProjectConflictError: Destino de un movimiento no válido.
        FolderNotSavedError, ForceRequiresAllFoldersError, OptionUnavailableError: Escaneo no válido.
    """
    project = access.project
    spec = OPERATIONS[params.operation]
    if ROLE_RANK[access.role] < ROLE_RANK[min_role(params)]:
        raise ProjectForbiddenError()
    active = select(func.count()).where(Run.created_by == actor.id, Run.status.in_(ACTIVE_RUN_STATUSES))
    if (db.scalar(active) or 0) >= MAX_ACTIVE_RUNS_PER_USER:
        raise TooManyRunsError(
            f"Tienes {MAX_ACTIVE_RUNS_PER_USER} ejecuciones en cola o en marcha; espera a que acaben."
        )
    if (
        spec.produces_artifacts
        and settings.user_quota_mb
        and quota_used_bytes(db, actor.id) >= settings.user_quota_mb * MB
    ):
        raise QuotaExceededError(f"Has llegado a tu cuota de {settings.user_quota_mb} MB en el workspace.")
    if isinstance(params, ProjectMoveParams):
        params = _validate_move(db, project, params, settings)
    if isinstance(params, ScanParams):
        params = _validate_scan(db, project, params, settings)
    if needs_preview(params):
        _check_preview(db, project, params)
    run = Run(
        id=str(uuid.uuid4()),
        project_id=project.id,
        operation=params.operation,
        queue=queue_for(params),
        is_write=is_write(params),
        params=stored_params(params),
        created_by=actor.id,
    )
    db.add(run)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise WriteLockedError("Espera a que termine la operación de escritura en curso.") from None
    audit.record(
        db,
        action=AuditAction.RUN_ENQUEUE,
        ctx=ctx,
        actor_id=actor.id,
        target_type="run",
        target_id=run.id,
        details={"project_id": project.id, "operation": run.operation, "dry_run": run.params.get("dry_run")},
    )
    db.commit()
    events.append(db, run.id, "status", {"status": "queued"})
    return run


def get_run(db: Session, run_id: str, user: User) -> tuple[Run, MemberRole | None]:
    """Run visible para ``user`` y su rol en el proyecto (``None`` en runs de sistema, solo para admin).

    Raises:
        RunNotFoundError: No existe o es de un proyecto que no ve.
    """
    try:
        run_id = str(uuid.UUID(run_id))
    except ValueError:
        raise RunNotFoundError() from None
    run = db.get(Run, run_id)
    if run is None:
        raise RunNotFoundError()
    if run.project_id is None:
        if user.role != "admin":
            raise RunNotFoundError()
        return run, None
    try:
        access = projects.get_access(db, run.project_id, user, include_deleted=True)
    except ProjectNotFoundError:
        raise RunNotFoundError() from None
    return run, access.role


def list_runs(
    db: Session,
    user: User,
    *,
    project_id: int | None,
    status: str | None,
    operation: str | None,
    limit: int,
    offset: int,
) -> tuple[list[Run], int]:
    """Runs visibles, más recientes primero."""
    query = select(Run)
    if user.role != "admin":
        query = query.where(Run.project_id.in_(projects.visible_project_ids(user)))
    if project_id is not None:
        query = query.where(Run.project_id == project_id)
    if status:
        query = query.where(Run.status == status)
    if operation:
        query = query.where(Run.operation == operation)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(Run.created_at.desc(), Run.id).limit(limit).offset(offset)).unique().all()
    return list(rows), total


def project_names(db: Session, project_ids: set[int]) -> dict[int, str]:
    """Nombre de cada proyecto de ``project_ids``."""
    if not project_ids:
        return {}
    rows = db.execute(select(Project.id, Project.name).where(Project.id.in_(project_ids))).all()
    return {row.id: row.name for row in rows}


def cancel(db: Session, run: Run, *, role: MemberRole | None, actor: User, ctx: RequestContext) -> Run:
    """Cancela un run en cola (al momento) o pide parar uno en marcha (lo atiende el worker).

    Raises:
        RunNotAllowedError: No lo lanzó y no es ``owner`` del proyecto (ni admin).
        RunFinishedError: Ya terminó.
    """
    if actor.role != "admin" and run.created_by != actor.id and role != "owner":
        raise RunNotAllowedError()
    if run.status in FINISHED_RUN_STATUSES:
        raise RunFinishedError()
    now = utcnow()
    # Condicional: si el worker lo reclama a la vez, gana el reclamo y se pide la cancelación al run en marcha.
    claimed = db.execute(
        update(Run)
        .where(Run.id == run.id, Run.status == "queued")
        .values(status="cancelled", finished_at=now, cancel_requested=True, cancel_reason="user")
    )
    if not claimed.rowcount:  # type: ignore[attr-defined]
        db.execute(
            update(Run)
            .where(Run.id == run.id, Run.status == "running")
            .values(cancel_requested=True, cancel_reason="user")
        )
    audit.record(
        db,
        action=AuditAction.RUN_CANCEL,
        ctx=ctx,
        actor_id=actor.id,
        target_type="run",
        target_id=run.id,
        details={"project_id": run.project_id, "operation": run.operation},
    )
    db.commit()
    if claimed.rowcount:  # type: ignore[attr-defined]
        events.append(db, run.id, "status", {"status": "cancelled"})
        events.append(db, run.id, "end", {"status": "cancelled"})
    else:
        events.append(db, run.id, "log", {"level": "info", "message": "Cancelación solicitada."})
    db.refresh(run)
    return run


def get_artifact(run: Run, artifact_id: int) -> Artifact:
    """Artefacto ``artifact_id`` de ``run``.

    Raises:
        ArtifactNotFoundError: No es de este run.
    """
    for artifact in run.artifacts:
        if artifact.id == artifact_id:
            return artifact
    raise ArtifactNotFoundError()
