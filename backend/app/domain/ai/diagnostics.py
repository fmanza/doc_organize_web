"""Diagnóstico del entorno (W4, «Administración → Diagnóstico»): ``check_environment`` de doc_organize en un
subproceso, con la comprobación de IA opcional sobre la familia ``litellm`` configurada.

Solo el admin de instancia: comprueba el servidor (Python, docling y sus modelos, extras, Zensical, GPU, LibreOffice,
audio y vídeo) y, con ``check_ai``, envía un texto sintético a los modelos configurados (gasta unos pocos tokens). El
informe no lleva claves, URL del proxy ni rutas del contenedor. Como mucho uno a la vez y uno cada
``MIN_INTERVAL_SECONDS``; cada diagnóstico se audita con su resultado, sin detalles.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Final

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import User
from app.domain.ai import settings as ai_settings
from app.domain.ai.errors import AiNotConfiguredError, DiagnosticsFailedError, DiagnosticsTooSoonError
from app.domain.identity import audit
from app.domain.identity import users as identity_users
from app.domain.identity.audit import AuditAction, RequestContext
from app.domain.runs import workers as run_workers
from app.integrations.doc_organize import models as library_models
from app.integrations.doc_organize.ai import TaskKey
from app.integrations.doc_organize.diagnostics import (
    AiEndpointSpec,
    DiagnosticCheck,
    DiagnosticsReport,
    run_diagnostics,
)

MIN_INTERVAL_SECONDS: Final = 30.0
#: Tareas cuyo modelo se prueba con ``check_ai``: las de clasificar, describir y diseñar la taxonomía siempre (con su
#: alias si no tienen modelo) y las de agentes y embeddings si tienen uno propio, como hace doc_organize con las variables
#: de entorno. Los embeddings se prueban pidiendo un vector (``AiEndpoint(kind="embedding")``, 2.0.0rc2).
ALWAYS: Final[tuple[TaskKey, ...]] = ("classify", "enrich", "taxonomy_design")

_lock = threading.Lock()
_last: list[float] = []


def clear_rate_limit() -> None:
    """Olvida el último diagnóstico (tests)."""
    _last.clear()


def _endpoints(db: Session, settings: Settings) -> list[AiEndpointSpec]:
    try:
        connection = ai_settings.connection(db, settings, "litellm")
    except AiNotConfiguredError:
        return []
    tasks: list[TaskKey] = list(ALWAYS)
    tasks += [task for task in ("agent", "embed") if connection.values.get(f"model_{task}")]
    return [
        AiEndpointSpec(
            name=task,
            base_url=connection.values["base_url"],
            virtual_key=connection.values.get(f"virtual_key_{task}") or connection.values["virtual_key"],
            model=connection.model_for(task),
            kind="embedding" if task == "embed" else "chat",
        )
        for task in tasks
    ]


def run(
    db: Session,
    settings: Settings,
    *,
    check_ai: bool,
    actor: User,
    ctx: RequestContext,
    clock: Callable[[], float] = time.monotonic,
) -> DiagnosticsReport:
    """Ejecuta el diagnóstico y lo audita.

    Raises:
        DiagnosticsTooSoonError: Hay otro en marcha o el último fue hace menos de ``MIN_INTERVAL_SECONDS``.
        DiagnosticsFailedError: El subproceso falló o no terminó a tiempo (sin detalles).
    """
    if not _lock.acquire(blocking=False):
        raise DiagnosticsTooSoonError("Ya hay un diagnóstico en marcha.")
    try:
        now = clock()
        if _last and now - _last[-1] < MIN_INTERVAL_SECONDS:
            raise DiagnosticsTooSoonError(
                f"Vuelve a intentarlo dentro de {int(MIN_INTERVAL_SECONDS - (now - _last[-1])) + 1} s."
            )
        _last[:] = [now]
        endpoints = _endpoints(db, settings) if check_ai else []
        redact = [
            str(path)
            for path in (settings.models_dir, settings.data_dir, settings.workspace_dir, settings.locations_root)
        ]
        try:
            report = run_diagnostics(
                check_ai=check_ai,
                endpoints=endpoints,
                artifacts_path=library_models.artifacts_path(settings.models_dir),
                redact=redact,
            )
        except RuntimeError as exc:
            raise DiagnosticsFailedError(str(exc)) from None
    finally:
        _lock.release()
    report = with_instance_admins(with_worker_gpu(report, db, settings), db)
    audit.record(
        db,
        action=AuditAction.ADMIN_DIAGNOSTICS,
        ctx=ctx,
        actor_id=actor.id,
        target_type="instance",
        target_id=None,
        details={
            "check_ai": check_ai,
            "ok": report.ok,
            "errors": [check.name for check in report.checks if check.status == "error"],
        },
    )
    db.commit()
    return report


def with_instance_admins(report: DiagnosticsReport, db: Session) -> DiagnosticsReport:
    """Añade la comprobación ``instance_admins`` (F0, 2.7): siempre debe haber un admin de instancia activo.

    Con la API no se puede llegar a cero; sí restaurando una copia o editando la BD. La recuperación es la CLI
    ``recover-admin`` o ``create-admin``.
    """
    count = identity_users.active_instance_admins(db)
    if count:
        check = DiagnosticCheck("instance_admins", "ok", f"{count} administrador(es) de la instancia activo(s)")
    else:
        check = DiagnosticCheck(
            "instance_admins",
            "error",
            "No hay ningún administrador de la instancia activo",
            "Recupera uno con «python -m app.cli recover-admin --username <usuario>» o crea otro con «create-admin».",
        )
    return DiagnosticsReport(checks=[*report.checks, check], checked_at=report.checked_at)


def with_worker_gpu(report: DiagnosticsReport, db: Session, settings: Settings) -> DiagnosticsReport:
    """La comprobación ``gpu`` con lo que publican los workers de la cola ``gpu``.

    ``check_environment`` corre en el proceso web, que no convierte ni tiene GPU (imagen de CPU): su resultado solo
    dice que la web no tiene GPU. Quien hace el OCR por GPU es el worker de la cola ``gpu``, que publica
    ``gpu_active`` en sus capacidades. Si hay alguno vivo, la comprobación dice si tiene GPU; si no, queda la de la web.
    """
    gpu_workers = [
        worker
        for worker in run_workers.list_workers(db)
        if "gpu" in (worker.queues or []) and run_workers.is_alive(worker, settings)
    ]
    if not gpu_workers:
        return report
    active = [worker for worker in gpu_workers if (worker.capabilities or {}).get("gpu_active")]
    if active:
        check = DiagnosticCheck(
            "gpu", "ok", f"GPU CUDA activa en {len(active)} de {len(gpu_workers)} worker(s) de la cola gpu"
        )
    else:
        check = DiagnosticCheck(
            "gpu",
            "warning",
            f"Ningún worker de la cola gpu ({len(gpu_workers)}) tiene una GPU CUDA activa: el OCR irá por CPU",
            "Comprueba los drivers NVIDIA del equipo y que el contenedor worker-gpu ve la GPU (nvidia-smi dentro).",
        )
    checks = [check if item.name == "gpu" else item for item in report.checks]
    if all(item.name != "gpu" for item in report.checks):
        checks.append(check)
    return DiagnosticsReport(checks=checks, checked_at=report.checked_at)
