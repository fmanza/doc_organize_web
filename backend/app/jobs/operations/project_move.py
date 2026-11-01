"""``project_move``: mueve la carpeta de salidas a una carpeta nueva de otra ubicación destino ``rw`` (o la misma).

En el mismo sistema de ficheros es un ``rename`` atómico. Entre sistemas de ficheros (p. ej. dos recursos de red):
copia con progreso → comprobación de recuento → borrado del origen. Si la copia falla o se cancela, se borra la copia
parcial y el proyecto no cambia; si falla el borrado del origen, el proyecto ya apunta al destino y se avisa de lo que
quedó. Todo el movimiento es una fase crítica: una cancelación no termina el subproceso (la copia la atiende entre
ficheros y deshace lo copiado). El estado (``cache.db``) no se mueve: vive en ``data`` (ADR-005).
"""

from __future__ import annotations

import errno
import logging
import os
import shutil
from pathlib import Path
from typing import Any

from sqlalchemy import update

from app.db.models import Location, Project, utcnow
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction
from app.domain.locations.paths import join_relative
from app.domain.projects import service as projects
from app.domain.projects.errors import InvalidProjectError, ProjectConflictError
from app.domain.runs.operations import ProjectMoveParams
from app.jobs.context import JobCancelled, JobContext, JobFailed
from app.jobs.operations._files import copy_tree, delete_tree, measure, project_paths, require_rw, resolve_in
from app.jobs.operations.common import WORKER_CONTEXT, require_project

logger = logging.getLogger(__name__)


def _destination(ctx: JobContext, project: Project, params: ProjectMoveParams) -> Location:
    with ctx.session_factory() as db:
        location = db.get(Location, params.destination_location_id)
        if location is None:
            raise JobFailed("location_missing", "La ubicación de destino ya no existe.")
        try:
            projects.check_destination_free(
                db,
                destination_location_id=location.id,
                destination_subpath=join_relative(params.destination_parent, params.new_folder),
                source_location_id=project.source_location_id,
                source_subpaths=project.source_subpaths,
                exclude_project_id=project.id,
            )
        except (InvalidProjectError, ProjectConflictError) as exc:
            raise JobFailed("destination_conflict", exc.detail or exc.title) from None
        db.expunge(location)
    require_rw(location)
    return location


def run(ctx: JobContext, params: ProjectMoveParams, project: Project | None) -> dict[str, Any]:
    """Comprueba y cuenta (``dry_run``) o mueve; devuelve recuentos, si es el mismo sistema de ficheros y el destino."""
    project = require_project(project)
    paths = project_paths(project, ctx)
    destination = _destination(ctx, project, params)
    parent = resolve_in(destination, params.destination_parent, ctx)
    target = parent.absolute / params.new_folder
    if target.exists():
        raise JobFailed("target_exists", f"Ya existe la carpeta «{params.new_folder}» en el destino.")
    source = paths.output.absolute
    same_fs = os.stat(source).st_dev == os.stat(parent.absolute).st_dev
    size = measure(source, ctx, "measure_outputs")
    free = shutil.disk_usage(parent.absolute).free
    result: dict[str, Any] = {
        "files": size.files,
        "bytes": size.bytes,
        "same_filesystem": same_fs,
        "free_bytes": free,
        "destination_location": destination.name,
        "destination_subpath": join_relative(parent.relative, params.new_folder),
    }
    if not same_fs and size.bytes > free:
        raise JobFailed("no_space", "No hay espacio suficiente en el destino.")
    if params.dry_run:
        return result
    ctx.check_cancelled()
    subpath = str(result["destination_subpath"])
    with ctx.uninterruptible():
        moved = False
        if same_fs:
            ctx.progress("move", 0, 1)
            try:
                os.mkdir(target)  # reserva: si alguien la crea a la vez, falla aquí y no se pisa nada
                os.rename(source, target)
                moved = True
            except FileExistsError:
                raise JobFailed("target_exists", f"Ya existe la carpeta «{params.new_folder}» en el destino.") from None
            except OSError as exc:
                if exc.errno != errno.EXDEV:
                    raise
                target.rmdir()  # mismo dispositivo, pero distinto montaje: se copia
            ctx.progress("move", 1, 1)
        if not moved:
            _copy(ctx, source, target, size.files)
        # El proyecto pasa al destino nuevo **antes** de borrar el anterior: si el borrado se corta, el proyecto ya
        # apunta a una copia completa y solo quedan restos en la carpeta antigua.
        _switch(ctx, project, destination, subpath, size.files, size.bytes)
        if not moved:
            leftovers = delete_tree(source, ctx, "delete_source", total=size.files)
            result["leftovers"] = len(leftovers)
            if leftovers:
                logger.warning("Restos en la carpeta anterior", extra={"run_id": ctx.run_id, "items": leftovers[:1000]})
                ctx.log(
                    f"El proyecto ya está en el destino, pero quedaron {len(leftovers)} elementos en la carpeta "
                    "anterior.",
                    level="warning",
                )
    return result


def _switch(ctx: JobContext, project: Project, destination: Location, subpath: str, files: int, size: int) -> None:
    with ctx.session_factory() as db:
        db.execute(
            update(Project)
            .where(Project.id == project.id)
            .values(destination_location_id=destination.id, destination_subpath=subpath, updated_at=utcnow())
        )
        audit.record(
            db,
            action=AuditAction.PROJECT_MOVE,
            ctx=WORKER_CONTEXT,
            actor_id=ctx.created_by,
            target_type="project",
            target_id=project.id,
            details={
                "run_id": ctx.run_id,
                "from": {"location_id": project.destination_location_id, "subpath": project.destination_subpath},
                "to": {"location_id": destination.id, "subpath": subpath},
                "files": files,
                "bytes": size,
            },
        )
        db.commit()


def _copy(ctx: JobContext, source: Path, target: Path, total: int) -> None:
    """Copia ``source`` en ``target``; si falla, se cancela o no cuadra, borra la copia parcial (el proyecto no cambia)."""
    try:
        copied = copy_tree(source, target, ctx, "copy", total=total)
    except JobCancelled:
        delete_tree(target, ctx, "rollback")
        raise
    except OSError as exc:
        logger.warning("Copia fallida al mover un proyecto", extra={"exc_type": type(exc).__name__})
        delete_tree(target, ctx, "rollback")
        raise JobFailed("copy_failed", "No se pudo copiar la carpeta al destino; el proyecto no ha cambiado.") from None
    if copied != total:
        delete_tree(target, ctx, "rollback")
        raise JobFailed("copy_mismatch", "La copia no coincide con el origen; el proyecto no ha cambiado.")
