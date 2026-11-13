"""``taxonomy_draft``: borrador de manifiesto de taxonomía con IA (WB-8.2b; sustituye a ``POST
.../context/taxonomy-manifest-draft`` de la web integrada).

Reúne los documentos convertidos de las carpetas de origen (igual que ``context_build``), envía una muestra de
``sample_size`` al servicio de IA y deja el borrador en el resultado del run. **No escribe nada** en el proyecto: el
usuario lo revisa en el editor y, si quiere, lo guarda con el ``PUT`` del manifiesto. Se audita, porque el contenido
de los documentos sale de la app.
"""

from __future__ import annotations

from typing import Any, Final

from app.db.models import Project
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction
from app.domain.runs.operations import MAX_TEMPLATE_BYTES, TaxonomyDraftParams
from app.integrations.doc_organize import ai as library_ai
from app.jobs.context import JobContext, JobFailed
from app.jobs.operations.common import WORKER_CONTEXT, require_project
from app.jobs.operations.context import ai_connection, context_folders

AI_ERRORS: Final[dict[str, str]] = {
    "ai_auth": "El servicio de IA rechazó la clave del borrador de manifiesto. Revisa la configuración de IA.",
    "ai_connection": "No se pudo conectar con el servicio de IA.",
    "ai_error": "El servicio de IA devolvió un error o una respuesta que no es un borrador de manifiesto válido.",
}


def run(ctx: JobContext, params: TaxonomyDraftParams, project: Project | None) -> dict[str, Any]:
    """Pide el borrador y lo devuelve como resultado del run (Markdown + resumen del catálogo)."""
    project = require_project(project)
    connection = ai_connection(ctx, "litellm_taxonomy_manifest_draft")
    _, folders, _ = context_folders(ctx, project)
    ctx.progress("ai_sample", 0, None)
    ctx.check_cancelled()
    ctx.progress("ai_request", 0, None)
    try:
        draft = library_ai.draft_manifest(
            connection, folders, params.sample_size, name=project.name, created_at=project.created_at
        )
    except library_ai.NoConvertedDocumentsError:
        raise JobFailed(
            "no_converted_documents", "El proyecto no tiene documentos convertidos: escanea antes de pedir un borrador."
        ) from None
    except library_ai.AiServiceError as exc:
        if exc.timed_out:  # conectó pero no respondió: no es un fallo de conexión (el modelo es lento)
            raise JobFailed(
                "ai_timeout",
                f"El servicio de IA no respondió a tiempo ({connection.timeout_s:g} s por intento). Sube «Tiempo"
                " máximo del borrador de IA» en los ajustes o usa un modelo más rápido.",
            ) from None
        raise JobFailed(exc.code, AI_ERRORS[exc.code]) from None
    if len(draft.markdown.encode("utf-8")) > MAX_TEMPLATE_BYTES:  # va a runs.result (config.db) y al editor
        raise JobFailed("ai_error", "El borrador de la IA supera el tamaño máximo de un manifiesto (256 KiB).")
    result: dict[str, Any] = {
        "manifest_markdown": draft.markdown,
        "reasoning": draft.reasoning,
        "sample_documents": draft.sample_documents,
        "total_documents": draft.total_documents,
        "domains": [{"slug": slug, "name": name} for slug, name in draft.domains],
        "material_types": [{"slug": slug, "name": name} for slug, name in draft.material_types],
    }
    with ctx.session_factory() as db:
        audit.record(
            db,
            action=AuditAction.PROJECT_TAXONOMY_DRAFT,
            ctx=WORKER_CONTEXT,
            actor_id=ctx.created_by,
            target_type="project",
            target_id=project.id,
            details={"run_id": ctx.run_id, "sample_documents": draft.sample_documents},
        )
        db.commit()
    ctx.progress("done", 1, 1)
    return result
