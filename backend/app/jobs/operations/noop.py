"""``noop``: prueba del motor de ejecuciones sin efectos en ficheros del proyecto (Fase 3).

Avanza ``steps`` pasos de ``step_seconds`` publicando progreso, atiende la cancelación entre pasos y deja un
artefacto de texto en el workspace del run.
"""

from __future__ import annotations

import time
from typing import Any

from app.db.models import Project
from app.domain.runs.operations import NoopParams
from app.jobs.context import JobContext, JobFailed

_SLICE = 0.2


def run(ctx: JobContext, params: NoopParams, project: Project | None) -> dict[str, Any]:
    """Ejecuta los pasos y devuelve ``{"steps": n}``."""
    ctx.progress("noop", 0, params.steps)
    for step in range(1, params.steps + 1):
        waited = 0.0
        while waited < params.step_seconds:
            ctx.check_cancelled()
            pause = min(_SLICE, params.step_seconds - waited)
            time.sleep(pause)
            waited += pause
        ctx.check_cancelled()
        if params.fail_at_step == step:
            raise JobFailed("noop_failed", f"Fallo simulado en el paso {step}.")
        ctx.progress("noop", step, params.steps, f"Paso {step}")
    output = ctx.workdir / "outputs" / "noop.txt"
    output.write_text(f"noop: {params.steps} pasos completados\n", encoding="utf-8")
    ctx.add_artifact("outputs/noop.txt")
    return {"steps": params.steps}
