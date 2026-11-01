"""Subproceso de un job (``multiprocessing`` *spawn*): recibe **solo el ``run_id``** y carga todo de la BD.

Escribe ``logs/run.log`` (JSON) y ``run.json`` en la carpeta del run, ejecuta la operación y cierra el run con su
estado final. Es el único proceso que llega a importar doc_organize (a través de la capa anticorrupción).
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.redact import PathRedactor, RedactingJsonFormatter, RunLogFilter
from app.db.models import Project, Run
from app.db.session import get_engine
from app.domain.runs.operations import RUN_PARAMS
from app.domain.settings.service import effective_settings
from app.jobs import queue
from app.jobs.context import JobCancelled, JobContext, JobFailed
from app.jobs.operations import REGISTRY
from app.workspace import runs as workspace

logger = logging.getLogger(__name__)

TIMEOUT_MESSAGE = "La operación superó el tiempo máximo; se guardó lo hecho hasta parar."
RUN_LOG_MAX_BYTES = 20 * 1024 * 1024


def container_redactor(settings: Settings) -> PathRedactor:
    """Etiquetas de las carpetas del contenedor para el ``run.log`` descargable."""
    return PathRedactor(
        [
            (str(settings.locations_root), "«ubicaciones»"),
            (str(settings.data_dir), "«datos»"),
            (str(settings.workspace_dir), "«workspace»"),
            (str(settings.models_dir), "«modelos»"),
            (sys.prefix, "«python»"),
        ]
    )


def _summary(run: Run, status: str, result: dict[str, Any] | None, error: str | None) -> dict[str, Any]:
    return {
        "run_id": run.id,
        "project_id": run.project_id,
        "operation": run.operation,
        "params": run.params,
        "status": status,
        "error_code": error,
        "result": result,
        "created_at": run.created_at,
        "started_at": run.started_at,
        "written_at": datetime.now().astimezone(),
    }


def main(run_id: str) -> None:
    """Ejecuta el run ``run_id`` (ya reclamado: ``running``) y lo cierra."""
    base_settings = get_settings()
    configure_logging(base_settings.log_level)
    factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    with factory() as db:
        run = db.get(Run, run_id)
        if run is None or run.status != "running":
            logger.warning("Run no reclamado o inexistente", extra={"run_id": run_id})
            return
        settings = effective_settings(db, base_settings)
        project = db.get(Project, run.project_id) if run.project_id is not None else None
        if project is not None:
            db.expunge(project)
        db.expunge(run)

    workdir = workspace.ensure(settings, run_id)
    # `run.log` se descarga (cualquier miembro del proyecto): sin rutas del contenedor ni trazas, solo los registros de
    # la aplicación y los avisos de las librerías, y con un tamaño máximo.
    file_handler = logging.handlers.RotatingFileHandler(
        workdir / workspace.LOG_REL, maxBytes=RUN_LOG_MAX_BYTES, backupCount=1, encoding="utf-8"
    )
    file_handler.setFormatter(RedactingJsonFormatter(container_redactor(settings)))
    file_handler.addFilter(RunLogFilter())
    logging.getLogger().addHandler(file_handler)
    logger.info("Run iniciado", extra={"run_id": run_id, "operation": run.operation})
    workspace.write_run_json(settings, run_id, _summary(run, "running", None, None))

    ctx = JobContext(
        run_id=run_id, settings=settings, session_factory=factory, workdir=workdir, created_by=run.created_by
    )
    ctx.start_cancel_watch()
    status = "failed"
    code: str | None = "internal"
    message: str | None = "Error interno al ejecutar la operación."
    result: dict[str, Any] | None = None
    try:
        params = RUN_PARAMS.validate_python(run.params)
        result = REGISTRY[run.operation](ctx, params, project)
        status, code, message = "succeeded", None, None
    except JobCancelled as exc:
        result = exc.result
        status, code, message = "cancelled", None, None
        with factory() as db:
            if db.scalar(select(Run.cancel_reason).where(Run.id == run_id)) == "timeout":
                status, code, message = "failed", "timeout", TIMEOUT_MESSAGE
    except JobFailed as exc:
        result = exc.result
        code, message = exc.code, exc.message
        logger.warning("Run fallido", extra={"run_id": run_id, "error_code": exc.code})
    except Exception as exc:  # noqa: BLE001 - cualquier fallo cierra el run; el detalle va al log, no al usuario
        logger.error("Error no controlado en el run", extra={"run_id": run_id, "exc_type": type(exc).__name__})
    finally:
        ctx.stop_cancel_watch()

    logger.info("Run terminado", extra={"run_id": run_id, "status": status})
    file_handler.close()
    logging.getLogger().removeHandler(file_handler)
    workspace.write_run_json(settings, run_id, _summary(run, status, result, code))
    if (workdir / workspace.LOG_REL).is_file():
        ctx.add_artifact(workspace.LOG_REL, name="run.log", kind="log")
    with factory() as db:
        if result is not None:
            db.execute(update(Run).where(Run.id == run_id).values(result=result))
            db.commit()
        queue.finish(db, run_id, status, code=code, message=message)
