"""``context_evaluate`` y ``context_dry_run``: calidad de la clasificación (W5, doc_organize 2.0 G3).

- **Evaluar**: el contexto guardado contra la referencia (el Excel subido o las decisiones del proyecto); el informe va
  en el resultado del run. No escribe nada.
- **Comparar cambios**: clasifica los documentos de la referencia con otra configuración (plantilla o manifiesto,
  modelo de clasificar, alcance de la IA o un perfil sin guardar) con ``dry_run_classify``, **sin guardar nada**, y lo
  compara con la evaluación del contexto actual. Con IA, ``max_documents`` acota los documentos enviados; se cancela
  entre documentos. Se audita, porque el contenido puede salir hacia la IA.
"""

from __future__ import annotations

from dataclasses import replace

from app.db.models import Project
from app.domain.context import quality
from app.domain.context.errors import GoldNotFoundError
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction
from app.domain.runs.operations import ContextDryRunParams, ContextEvaluateParams
from app.domain.runs.results import ContextDryRunResult, ContextEvaluateResult
from app.integrations.doc_organize import evaluation as library
from app.integrations.doc_organize.context import TemplateInvalidError
from app.integrations.doc_organize.projects import DocOrganizeOperationError
from app.jobs.context import JobCancelled, JobContext, JobFailed
from app.jobs.operations.common import WORKER_CONTEXT, require_project
from app.jobs.operations.context import ai_connection, context_folders


def _gold(ctx: JobContext, project: Project, source: library.GoldSource) -> library.GoldSpec:
    try:
        return quality.gold_spec(ctx.settings, project, source)
    except GoldNotFoundError:
        raise JobFailed("gold_not_found", "La referencia ya no está: súbela de nuevo.") from None


def run_evaluate(ctx: JobContext, params: ContextEvaluateParams, project: Project | None) -> ContextEvaluateResult:
    """Evalúa el contexto guardado y devuelve el informe."""
    project = require_project(project)
    output, folders, _ = context_folders(ctx, project)
    spec = _gold(ctx, project, params.gold)
    ctx.progress("quality_evaluate", 0, None)
    ctx.check_cancelled()
    try:
        report = library.evaluate(output, folders, spec, name=project.name, created_at=project.created_at)
    except library.GoldInvalidError as exc:
        raise JobFailed("gold_invalid", f"La referencia no sirve: {exc}") from None
    except DocOrganizeOperationError as exc:
        raise JobFailed("context_failed", str(exc)) from None
    ctx.progress("done", 1, 1)
    return ContextEvaluateResult(gold=params.gold, report=report)


def run_dry_run(ctx: JobContext, params: ContextDryRunParams, project: Project | None) -> ContextDryRunResult:
    """Clasificación de prueba con la configuración candidata, comparada con el contexto actual."""
    project = require_project(project)
    output, folders, namer = context_folders(ctx, project)
    spec = _gold(ctx, project, params.gold)
    ai = None
    if params.ai_scope != "off":
        ai = ai_connection(ctx, "litellm")
        values = dict(ai.values)
        if params.model_classify:
            values["model_classify"] = params.model_classify
        values["budget_classify"] = str(params.max_documents)
        ai = replace(ai, values=values, redact_credentials=project.ai_redact_credentials)
    request = library.DryRunRequest(
        name=project.name,
        created_at=project.created_at,
        output_root=output,
        folders=folders,
        gold=spec,
        manifest_markdown=params.template_markdown,
        template_name=params.template_name,
        ai=ai,
        ai_scope=params.ai_scope,
        profile_markdown=params.profile_markdown,
        versions=project.context_versions,
        version_across_extensions=project.context_versions_across_extensions,
    )

    def on_progress(phase: str, processed: int, total: int | None) -> None:
        ctx.progress(phase, processed, total)

    ctx.check_cancelled()
    try:
        comparison = library.dry_run(request, on_progress=on_progress, is_cancelled=lambda: ctx.cancelled)
    except library.GoldInvalidError as exc:
        raise JobFailed("gold_invalid", f"La referencia no sirve: {exc}") from None
    except TemplateInvalidError as exc:
        raise JobFailed(
            "template_invalid", f"La plantilla o el manifiesto no son válidos: {namer.text(str(exc))}"
        ) from None
    except DocOrganizeOperationError as exc:
        raise JobFailed("context_failed", str(exc)) from None
    if comparison is None:
        raise JobCancelled()
    result = ContextDryRunResult.model_validate(
        comparison
        | {
            "gold": params.gold,
            "catalog": params.catalog,
            "template_name": params.template_name,
            "ai_scope": params.ai_scope,
            "profile_changed": params.profile_markdown is not None,
        }
    )
    stopped = result.ai.stopped if result.ai else None
    if stopped:
        ctx.log(f"La IA se detuvo ({stopped}): la comparación es parcial.", level="warning")
    with ctx.session_factory() as db:
        audit.record(
            db,
            action=AuditAction.PROJECT_DRY_RUN,
            ctx=WORKER_CONTEXT,
            actor_id=ctx.created_by,
            target_type="project",
            target_id=project.id,
            details={
                "run_id": ctx.run_id,
                "documents": result.documents,
                "ai_scope": params.ai_scope,
                "calls": result.ai.calls if result.ai else None,
            },
        )
        db.commit()
    ctx.progress("done", 1, 1)
    return result
