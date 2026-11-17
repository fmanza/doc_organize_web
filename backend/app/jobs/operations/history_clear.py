"""``history_clear``: vacía las salidas y el estado de doc_organize del proyecto (``ProjectHistoryCleaner``, L-5).

Con ``dry_run`` solo cuenta lo que se borraría. La ejecución real llega con una vista previa confirmada (la valida la
API) y vuelve a comprobar que el destino es ``rw``.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Any

from sqlalchemy import delete

from app.db.models import Project, ProjectContext
from app.domain.context import manifest_versions
from app.domain.context.service import MAX_VERSION_BYTES
from app.domain.documents.errors import OutputNotFoundError, OutputTooLargeError
from app.domain.documents.service import read_inside
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction
from app.domain.runs.operations import HistoryClearParams
from app.integrations.doc_organize import DocOrganizeOperationError, clear_project_history
from app.integrations.doc_organize import context as library
from app.jobs.context import JobContext, JobFailed
from app.jobs.operations._files import measure, project_paths, require_rw
from app.jobs.operations.common import WORKER_CONTEXT, require_project


def run(ctx: JobContext, params: HistoryClearParams, project: Project | None) -> dict[str, Any]:
    """Cuenta (``dry_run``) o vacía el histórico; devuelve los recuentos de salidas y estado."""
    project = require_project(project)
    paths = project_paths(project, ctx)
    outputs = measure(paths.output.absolute, ctx, "measure_outputs")
    state = measure(paths.state, ctx, "measure_state")
    result: dict[str, Any] = {
        "output_files": outputs.files,
        "output_bytes": outputs.bytes,
        "state_files": state.files,
        "state_bytes": state.bytes,
    }
    if params.dry_run:
        return result
    require_rw(project.destination_location)
    ctx.check_cancelled()
    _keep_manifest_version(ctx, project, paths.output.absolute)
    ctx.progress("clear", 0, None)
    paths.state.mkdir(parents=True, exist_ok=True)
    with ctx.uninterruptible():
        try:
            clear_project_history(paths.output.absolute, paths.state, name=project.name, created_at=project.created_at)
        except DocOrganizeOperationError as exc:
            raise JobFailed("clear_failed", str(exc)) from None
    ctx.progress("clear", 1, 1)
    with ctx.session_factory() as db:
        # Vaciar las salidas borra también el contexto (context.json, carpeta reorganizada y sitio): fuera su proyección.
        db.execute(delete(ProjectContext).where(ProjectContext.project_id == project.id))
        audit.record(
            db,
            action=AuditAction.PROJECT_HISTORY_CLEAR,
            ctx=WORKER_CONTEXT,
            actor_id=ctx.created_by,
            target_type="project",
            target_id=project.id,
            details={"run_id": ctx.run_id, **result},
        )
        db.commit()
    return result


def _keep_manifest_version(ctx: JobContext, project: Project, output: Path) -> None:
    """Vaciar borra también ``taxonomy_manifest.md``: antes se guarda como versión (``history_clear``, 1.8.0) para
    poder restaurarlo. Solo un fichero normal dentro de la carpeta (un enlace o una carpeta en su lugar no se lee)."""
    path = library.manifest_file(output)
    try:
        if not stat.S_ISREG(os.lstat(path).st_mode):
            return
        data = read_inside(path, output, max_bytes=MAX_VERSION_BYTES)
    except (FileNotFoundError, OutputNotFoundError):
        return
    except OutputTooLargeError:
        ctx.log("El manifiesto es demasiado grande para guardarlo como versión: se borra sin versión.", level="warning")
        return
    with ctx.session_factory() as db:
        manifest_versions.add_version(
            db,
            project.id,
            manifest_versions.normalize(data.decode("utf-8", errors="replace")),
            "history_clear",
            actor_id=ctx.created_by,
        )
        db.commit()
