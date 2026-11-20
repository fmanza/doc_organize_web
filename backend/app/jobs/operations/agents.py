"""``taxonomy_agent`` y ``taxonomy_check``: diseñar y comprobar la taxonomía (W7, doc_organize 2.0.0rc1 M8).

- **Diseñar con IA**: ``TaxonomyDesignAgent`` (tarea ``agent``) mejora el manifiesto o la plantilla de partida (o
  diseña uno) con cambios pequeños comprobados por reglas contra todos los documentos. Se cancela entre pasos
  (``CancelToken``) y tiene un tope de pasos; **no guarda nada**: la propuesta, el mejor borrador y los informes van en
  el resultado para que una persona los revise y, si quiere, los guarde (manifiesto con ``If-Match`` y versiones, o
  plantilla con ``templates.manage``). Se audita: el contenido de los documentos sale hacia la IA.
- **Comprobar por reglas**: ``check_taxonomy_rules`` del Markdown del editor (aunque no esté guardado), sin IA.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from sqlalchemy import delete

from app.db.models import ContextReviewProposal, Project
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction
from app.domain.runs.operations import (
    ContextAuditParams,
    ContextReviewAgentParams,
    TaxonomyAgentParams,
    TaxonomyCheckParams,
)
from app.integrations.doc_organize import agents as library
from app.integrations.doc_organize.context import TemplateInvalidError
from app.integrations.doc_organize.projects import DocOrganizeOperationError
from app.jobs.context import JobCancelled, JobContext, JobFailed
from app.jobs.operations.common import WORKER_CONTEXT, require_project
from app.jobs.operations.context import ai_connection, context_folders

#: Avisos de por qué paró el agente sin terminar.
STOPPED: dict[str, str] = {
    "max_steps": "El agente llegó al tope de pasos sin terminar: se conserva su último borrador.",
    "max_tokens": "El agente llegó al tope de tokens sin terminar: se conserva su último borrador.",
    "max_tool_calls": "El agente llegó al tope de herramientas sin terminar: se conserva su último borrador.",
    "invalid_answer": "El agente no dio una respuesta válida: se conserva su último borrador.",
}


def run_design(ctx: JobContext, params: TaxonomyAgentParams, project: Project | None) -> dict[str, Any]:
    """Pide la propuesta al diseñador y la devuelve sin guardar nada."""
    project = require_project(project)
    output, folders, namer = context_folders(ctx, project)
    connection = replace(ai_connection(ctx, "litellm"), redact_credentials=project.ai_redact_credentials)
    request = library.DesignRequest(
        output_root=output,
        folders=folders,
        connection=connection,
        base_markdown=params.template_markdown,
        instructions=params.instructions,
        max_steps=params.max_steps,
    )
    ctx.check_cancelled()
    try:
        result = library.design_taxonomy(
            request,
            on_progress=lambda phase: ctx.progress(phase, 0, None),
            is_cancelled=lambda: ctx.cancelled,
            on_step=lambda done, total: ctx.progress("agent_run", done, total),
        )
    except library.NoDocumentsError:
        raise JobFailed(
            "no_converted_documents", "El proyecto no tiene documentos convertidos: escanea antes de diseñar."
        ) from None
    except TemplateInvalidError as exc:
        raise JobFailed("template_invalid", f"El manifiesto de partida no es válido: {namer.text(str(exc))}") from None
    except DocOrganizeOperationError as exc:
        raise JobFailed("ai_error", str(exc)) from None
    if result["stop_reason"] == "cancelled":
        raise JobCancelled(result)
    if result["stop_reason"] in STOPPED:
        ctx.log(STOPPED[result["stop_reason"]], level="warning")
    ctx.log(
        f"Agente: {result['steps']} pasos, {result['tool_calls']} herramientas y "
        f"{result['prompt_tokens'] + result['completion_tokens']} tokens en {result['duration_s']} s."
    )
    result |= {"catalog": params.catalog, "template_name": params.template_name}
    with ctx.session_factory() as db:
        audit.record(
            db,
            action=AuditAction.PROJECT_TAXONOMY_AGENT,
            ctx=WORKER_CONTEXT,
            actor_id=ctx.created_by,
            target_type="project",
            target_id=project.id,
            details={
                "run_id": ctx.run_id,
                "stop_reason": result["stop_reason"],
                "steps": result["steps"],
                "documents": result["documents"],
            },
        )
        db.commit()
    ctx.progress("done", 1, 1)
    return result


def run_check(ctx: JobContext, params: TaxonomyCheckParams, project: Project | None) -> dict[str, Any]:
    """Comprueba el manifiesto por reglas, sin IA."""
    project = require_project(project)
    _, folders, namer = context_folders(ctx, project)
    ctx.progress("agent_corpus", 0, None)
    ctx.check_cancelled()
    try:
        report = library.check_rules(params.markdown, folders)
    except library.NoDocumentsError:
        raise JobFailed(
            "no_converted_documents", "El proyecto no tiene documentos convertidos: escanea antes de comprobar."
        ) from None
    except TemplateInvalidError as exc:
        raise JobFailed("template_invalid", f"El manifiesto no es válido: {namer.text(str(exc))}") from None
    ctx.progress("done", 1, 1)
    return {"report": report}


def run_review(ctx: JobContext, params: ContextReviewAgentParams, project: Project | None) -> dict[str, Any]:
    """Pide propuestas al revisor y las guarda como pendientes (sustituyen a las pendientes anteriores). No aplica
    ninguna (D14): las acepta o descarta una persona en «Revisar clasificación»."""
    project = require_project(project)
    output, folders, namer = context_folders(ctx, project)
    connection = replace(ai_connection(ctx, "litellm"), redact_credentials=project.ai_redact_credentials)
    request = library.ReviewRequest(
        name=project.name,
        created_at=project.created_at,
        output_root=output,
        folders=folders,
        connection=connection,
        max_items=params.max_items,
        max_steps=params.max_steps,
        instructions=params.instructions,
    )
    ctx.progress("agent_run", 0, None)
    ctx.check_cancelled()
    try:
        result = library.review(
            request,
            is_cancelled=lambda: ctx.cancelled,
            on_step=lambda done, total: ctx.progress("agent_run", done, total),
        )
    except DocOrganizeOperationError as exc:
        raise JobFailed("ai_error", namer.text(str(exc))) from None
    if result["stop_reason"] == "cancelled":
        raise JobCancelled({k: v for k, v in result.items() if k != "proposals"})
    proposals = result.pop("proposals")
    with ctx.session_factory() as db:
        db.execute(
            delete(ContextReviewProposal).where(
                ContextReviewProposal.project_id == project.id, ContextReviewProposal.status == "pending"
            )
        )
        db.add_all(
            ContextReviewProposal(
                project_id=project.id,
                run_id=ctx.run_id,
                document_key=str(item["document_key"])[:4096],
                action=str(item["action"]),
                axes=dict(item.get("axes") or {}),
                rationale=item.get("rationale") or None,
                evidence=item.get("evidence") or None,
                source_sha256=item.get("source_sha256"),
                proposal_key=str(item.get("id") or "")[:64] or None,
            )
            for item in proposals
        )
        audit.record(
            db,
            action=AuditAction.PROJECT_REVIEW_AGENT,
            ctx=WORKER_CONTEXT,
            actor_id=ctx.created_by,
            target_type="project",
            target_id=project.id,
            details={"run_id": ctx.run_id, "stop_reason": result["stop_reason"], "proposals": len(proposals)},
        )
        db.commit()
    if result["stop_reason"] in STOPPED:
        ctx.log(
            STOPPED[result["stop_reason"]].replace("su último borrador", "las propuestas ya hechas"), level="warning"
        )
    ctx.log(f"Revisor: {len(proposals)} propuestas de {result['reviewed']} documentos revisados.")
    ctx.progress("done", 1, 1)
    return {**result, "proposals": len(proposals)}


def run_audit(ctx: JobContext, params: ContextAuditParams, project: Project | None) -> dict[str, Any]:
    """Informe del auditor de la taxonomía, sin IA."""
    del params
    project = require_project(project)
    output, _, namer = context_folders(ctx, project)
    ctx.progress("agent_corpus", 0, None)
    try:
        report = library.audit(output, name=project.name, created_at=project.created_at)
    except DocOrganizeOperationError as exc:
        raise JobFailed("context_failed", namer.text(str(exc))) from None
    ctx.progress("done", 1, 1)
    return {"audit": report}
