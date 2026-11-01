"""``project_delete``: borra el proyecto (lógico en la BD), su estado y, con ``delete_outputs``, su carpeta de salidas.

La carpeta de salidas pertenece al proyecto (nueva o vacía al crearlo), así que borrarla entera no toca ficheros
ajenos. Con ``dry_run`` solo cuenta lo que se borraría.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import update

from app.db.models import Project, utcnow
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction
from app.domain.projects.service import state_dir
from app.domain.runs.operations import ProjectDeleteParams
from app.jobs.context import JobContext
from app.jobs.operations._files import delete_tree, measure, project_paths, require_rw
from app.jobs.operations.common import WORKER_CONTEXT, require_project

logger = logging.getLogger(__name__)


def run(ctx: JobContext, params: ProjectDeleteParams, project: Project | None) -> dict[str, Any]:
    """Cuenta (``dry_run``) o borra; devuelve los recuentos y, si quedó algo sin borrar, cuántos elementos."""
    project = require_project(project)
    paths = project_paths(project, ctx) if params.delete_outputs else None
    outputs = measure(paths.output.absolute, ctx, "measure_outputs") if paths else None
    state_root = state_dir(ctx.settings, project.id)
    state = measure(state_root, ctx, "measure_state")
    result: dict[str, Any] = {
        "delete_outputs": params.delete_outputs,
        "output_files": outputs.files if outputs else None,
        "output_bytes": outputs.bytes if outputs else None,
        "state_files": state.files,
        "state_bytes": state.bytes,
    }
    if params.dry_run:
        return result
    ctx.check_cancelled()
    if paths:
        require_rw(project.destination_location)
    with ctx.uninterruptible():
        # Primero se marca como borrado: si el borrado de ficheros se corta, el proyecto no queda activo a medias.
        with ctx.session_factory() as db:
            db.execute(update(Project).where(Project.id == project.id).values(status="deleted", deleted_at=utcnow()))
            db.commit()
        leftovers: list[str] = []
        if paths and outputs:
            leftovers += delete_tree(paths.output.absolute, ctx, "delete_outputs", total=outputs.files)
        if state_root.exists():
            leftovers += [f"estado/{p}" for p in delete_tree(state_root, ctx, "delete_state", total=state.files)]
    if leftovers:
        logger.warning("Restos tras borrar el proyecto", extra={"run_id": ctx.run_id, "items": leftovers[:1000]})
        ctx.log(f"No se pudieron borrar {len(leftovers)} elementos; revisa el registro del run.", level="warning")
    result["leftovers"] = len(leftovers)
    with ctx.session_factory() as db:
        audit.record(
            db,
            action=AuditAction.PROJECT_DELETE,
            ctx=WORKER_CONTEXT,
            actor_id=ctx.created_by,
            target_type="project",
            target_id=project.id,
            details={"run_id": ctx.run_id, "name": project.name, **result},
        )
        db.commit()
    return result
