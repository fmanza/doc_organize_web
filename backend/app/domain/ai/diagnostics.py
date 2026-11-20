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
from app.domain.identity.audit import AuditAction, RequestContext
from app.integrations.doc_organize import models as library_models
from app.integrations.doc_organize.ai import TaskKey
from app.integrations.doc_organize.diagnostics import AiEndpointSpec, DiagnosticsReport, run_diagnostics

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
