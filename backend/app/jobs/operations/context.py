"""``context_build`` y ``context_delete``: contexto del proyecto con doc_organize 0.14.0 (WB-7.2, WB-7.3; L-8).

- **Construir**: documentos convertidos con éxito de las cachés de todas las carpetas de origen cuyo original sigue
  ahí; clasificación por dominios (descubiertos, catálogo propio, plantilla o manifiesto: el Markdown lo fija la API
  al encolar); copia a la carpeta reorganizada sin seguir enlaces (G27; un documento que falla no para al resto) y
  sitio Zensical. Al terminar, el resumen y los documentos se proyectan en ``project_contexts`` y
  ``context_documents`` (decisión C3) con rutas relativas. La cancelación se atiende antes de clasificar y antes de
  copiar; la copia y el sitio no se interrumpen a medias.
- **Borrar**: la carpeta reorganizada, el sitio, ``context.json`` y ``domains/`` (nunca ``Conversión/``). Con
  ``dry_run`` solo cuenta lo que se borraría; la ejecución real llega con una vista previa confirmada (regla 7).
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path, PurePosixPath
from typing import Any, Final

from sqlalchemy import delete, insert, update

from app.db.models import (
    ContextDocument,
    ContextDocumentAxisValue,
    ContextReviewItem,
    Project,
    ProjectContext,
    Run,
    utcnow,
)
from app.domain.ai import settings as ai_settings
from app.domain.ai.errors import AiNotConfiguredError
from app.domain.documents.paths import DocumentNamer
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction
from app.domain.runs.operations import ContextBuildParams, ContextDeleteParams, context_ai_tasks
from app.domain.runs.results import (
    AiPhaseResult,
    ContextBuildResult,
    ContextDeleteResult,
    SemanticResult,
    parse_result_as,
)
from app.domain.scan.state import folder_cache
from app.integrations import doc_organize as library
from app.integrations.doc_organize.ai import AiConnection, FamilyKey
from app.integrations.doc_organize.context import ContextDoc, ContextOutcome, ContextRequest, SourceFolder
from app.jobs.context import JobCancelled, JobContext, JobFailed
from app.jobs.operations._files import TreeSize, exclusion_filter, measure, project_paths, require_rw, source_folders
from app.jobs.operations.common import WORKER_CONTEXT, require_project

#: Documentos fallidos que se guardan en el resultado del run (el total va en ``failed``).
MAX_FAILED_SHOWN: Final = 100
#: Versiones antiguas (``current_only``) que se guardan con su ruta (el total va en ``superseded_count``).
MAX_SUPERSEDED: Final = 500
#: Filas de ``context_documents`` por ``INSERT``.
BATCH: Final = 1000


def _row(project_id: int, seq: int, doc: ContextDoc, namer: DocumentNamer) -> dict[str, Any]:
    # Fuera de las carpetas (no debería pasar: la caché se filtra por carpeta) solo queda el nombre del fichero.
    folder, path = namer.split(doc.source_path) or ("", PurePosixPath(doc.source_path.replace("\\", "/")).name)
    return {
        "project_id": project_id,
        "seq": seq,
        "domain_slug": doc.domain_slug,
        "title": doc.title[:1024],
        "document_type": (doc.document_type or "")[:64] or None,
        "material_type": doc.material_type,
        "material_type_name": doc.material_type_name,
        "folder": folder,
        "path": path,
        "organized_path": doc.organized_path,
        "failed": doc.failed,
        "classified_by": doc.classified_by if doc.domain_slug is not None else None,
        # 1.5.0: recortes defensivos al tamaño de las columnas (doc_organize ya limita la justificación a 500).
        "author": _cut(doc.author, 500),
        "description": doc.description,
        "keywords": doc.keywords,
        "language": _cut(doc.language, 8),
        "ai_filled": doc.ai_filled,
        "rules_domain": _cut(doc.rules_domain, 128),
        "rules_confidence": doc.rules_confidence,
        "ai_domain": _cut(doc.ai_domain, 128),
        "ai_confidence": doc.ai_confidence,
        "ai_reasoning": _cut(doc.ai_reasoning, 500),
        "material_type_confidence": doc.material_type_confidence,
        "unclassified_reason": doc.unclassified_reason if doc.domain_slug is None else None,
        # W5: clave de las decisiones, huella del original y versión.
        "document_key": doc.document_key,
        "source_sha256": _cut(doc.source_sha256, 64),
        "version": _cut(doc.version, 64),
        # La clave del grupo lleva la carpeta del contenedor: se guarda sin ella, como el resto de rutas.
        "version_group": namer.text(doc.version_group) if doc.version_group else None,
        "is_current": doc.is_current,
    }


def _axis_rows(project_id: int, seq: int, doc: ContextDoc) -> list[dict[str, Any]]:
    """Filas de ``context_document_axis_values`` del documento (un valor repetido en un eje cuenta una vez)."""
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    for value in doc.axes:
        key = (value.axis[:41], value.slug[:128])
        rows.setdefault(
            key,
            {
                "project_id": project_id,
                "seq": seq,
                "axis": key[0],
                "slug": key[1],
                "name": value.name[:256],
                "confidence": value.confidence,
                "classified_by": _cut(value.classified_by, 8),
                "evidence_verified": value.evidence_verified,
                "evidence": _cut(value.evidence, 500),
            },
        )
    return list(rows.values())


def _cut(value: str | None, size: int) -> str | None:
    return value[:size] if value else None


def _project_rows(
    ctx: JobContext, project: Project, params: ContextBuildParams, outcome: ContextOutcome, namer: DocumentNamer
) -> None:
    """Sustituye la proyección del contexto del proyecto por la de ``outcome`` en una transacción.

    Las filas se preparan antes de abrirla y se insertan con ``executemany`` por lotes: con 100 000 documentos la
    escritura en ``config.db`` dura poco y no bloquea al resto (eventos de otros runs, sesiones).
    """
    rows = [_row(project.id, seq, doc, namer) for seq, doc in enumerate(outcome.documents)]
    seq_by_key = {doc.document_key: seq for seq, doc in enumerate(outcome.documents) if doc.document_key}
    review_rows = [
        {
            "project_id": project.id,
            "seq": seq_by_key.get(item["document_key"]),
            "document_key": str(item["document_key"])[:4096],
            "reason": item["reason"],
            "priority": int(item["priority"]),
            "axis": _cut(item.get("axis"), 41),
            "value": _cut(item.get("value"), 128),
            "confidence": item.get("confidence"),
            "detail": _cut(namer.text(item["detail"]) if item.get("detail") else None, 1000),
        }
        for item in outcome.review
    ]
    axis_rows = [row for seq, doc in enumerate(outcome.documents) for row in _axis_rows(project.id, seq, doc)]
    with ctx.session_factory() as db:
        db.execute(delete(ContextReviewItem).where(ContextReviewItem.project_id == project.id))
        db.execute(delete(ContextDocumentAxisValue).where(ContextDocumentAxisValue.project_id == project.id))
        db.execute(delete(ContextDocument).where(ContextDocument.project_id == project.id))
        db.execute(delete(ProjectContext).where(ProjectContext.project_id == project.id))
        db.add(
            ProjectContext(
                project_id=project.id,
                output_folder_name=outcome.output_folder_name,
                catalog_kind=params.catalog,
                taxonomy_template_name=params.template_name if params.catalog == "template" else None,
                documents_count=sum(1 for d in outcome.documents if d.domain_slug is not None),
                unclassified_count=sum(1 for d in outcome.documents if d.domain_slug is None),
                failed_count=len(outcome.failed),
                site_built=outcome.site_built,
                ai_classification=params.ai_classification,
                built_with_version=_cut(outcome.built_with_version, 128),
                ai_classification_model=_cut(outcome.ai_classification_model, 128),
                ai_enrichment_model=_cut(outcome.ai_enrichment_model, 128),
                domains=outcome.domains,
                taxonomy_axes=outcome.taxonomy_axes,
                ai_provenance=outcome.ai_provenance,
                decisions_applied=outcome.decisions_applied,
                stale_decisions=outcome.stale_decisions,
                orphan_decisions=outcome.orphan_decisions,
                versions_mode=outcome.versions_mode,
                versions_across_extensions=outcome.versions_across_extensions,
                version_groups=[
                    {
                        **group,
                        "key": namer.text(group["key"]),
                        "members": [namer.display(path) for path in group["members"]],
                        "current": namer.display(group["current"]),
                    }
                    for group in outcome.version_groups
                ],
                superseded=[namer.display(path) for path in outcome.superseded[:MAX_SUPERSEDED]],
                superseded_count=len(outcome.superseded),
                built_by_run_id=ctx.run_id,
                built_at=utcnow(),
            )
        )
        db.flush()
        for start in range(0, len(rows), BATCH):
            db.execute(insert(ContextDocument), rows[start : start + BATCH])
        for start in range(0, len(axis_rows), BATCH):
            db.execute(insert(ContextDocumentAxisValue), axis_rows[start : start + BATCH])
        for start in range(0, len(review_rows), BATCH):
            db.execute(insert(ContextReviewItem), review_rows[start : start + BATCH])
        db.commit()


#: Ejemplos de cada lista de la frescura que se guardan (el total va en el recuento).
FRESHNESS_EXAMPLES: Final = 10


def refresh_freshness(ctx: JobContext, project: Project) -> dict[str, Any] | None:
    """Comprueba si el contexto sigue al día respecto a las cachés y lo guarda en ``project_contexts.freshness``.

    Sin contexto proyectado no hace nada (``None``). Lo llaman la construcción (al terminar) y el escaneo (la caché
    cambió). Las rutas se guardan relativas (``namer.display``), nunca las del contenedor.
    """
    with ctx.session_factory() as db:
        if db.get(ProjectContext, project.id) is None:
            return None
    output, folders, namer = context_folders(ctx, project)
    report = library.context.context_freshness(output, folders, name=project.name, created_at=project.created_at)
    if report is None:
        return None
    lists = {"changed": report.changed, "added": report.added, "removed": report.removed, "unknown": report.unknown}
    freshness: dict[str, Any] = {
        "checked_at": utcnow().isoformat(),
        "up_to_date": report.up_to_date,
        "stale_site": report.stale_site,
        **{key: len(paths) for key, paths in lists.items()},
        "examples": {key: [namer.display(p) for p in paths[:FRESHNESS_EXAMPLES]] for key, paths in lists.items()},
    }
    with ctx.session_factory() as db:
        db.execute(update(ProjectContext).where(ProjectContext.project_id == project.id).values(freshness=freshness))
        db.commit()
    return freshness


def context_folders(ctx: JobContext, project: Project) -> tuple[Path, list[SourceFolder], DocumentNamer]:
    """Carpeta del proyecto en el destino, carpetas de origen con su caché y conversiones, y el nombrador de rutas."""
    paths = project_paths(project, ctx)
    output = paths.output.absolute
    folders = source_folders(ctx, project)
    namer = DocumentNamer([(subpath, [root]) for subpath, root in folders], project.source_location.name)
    # Web 2.7 (ADR-017): lo excluido que siga en la caché no entra en el contexto ni en lo que lo lee.
    excluder = exclusion_filter(ctx, project, [root for _, root in folders])
    skip = None if excluder.empty else excluder.covers
    return (
        output,
        [
            SourceFolder(
                folder=subpath,
                root=root,
                cache_db=folder_cache(paths.state, subpath),
                conversion_dir=library.conversion_dir(output, paths.state, subpath),
                skip=skip,
            )
            for subpath, root in folders
        ],
        namer,
    )


def ai_connection(ctx: JobContext, family: FamilyKey) -> AiConnection:
    """Configuración de la familia ``family``, descifrada aquí, en el subproceso (ADR-004 §5).

    Raises:
        JobFailed: ``ai_not_configured`` si se quitó la configuración después de encolar.
    """
    with ctx.session_factory() as db:
        try:
            return ai_settings.connection(db, ctx.settings, family)
        except AiNotConfiguredError:
            raise JobFailed("ai_not_configured", "La IA de esta operación ya no está configurada.") from None


#: Avisos de por qué la IA dejó de clasificar en un run.
AI_STOPPED: Final[dict[str, str]] = {
    "auth": "El servicio de IA rechazó la clave: no se clasificó nada más con IA. Revisa la configuración.",
    "connection": "No se pudo conectar con el servicio de IA varias veces seguidas: no se clasificó nada más con IA.",
    "budget": (
        "Se llegó al máximo de documentos con IA por ejecución (presupuesto de la tarea o ajuste"
        " ai_max_documents_per_run)."
    ),
}
#: Lo mismo para las descripciones con IA (1.5.0): el resto se queda con lo que declara el documento.
ENRICHMENT_STOPPED: Final[dict[str, str]] = {
    "auth": "El servicio de IA rechazó la clave de las descripciones: no se completó nada más con IA.",
    "connection": "No se pudo conectar varias veces seguidas con la IA de las descripciones: no se completó nada más.",
    "budget": (
        "Las descripciones con IA llegaron al máximo de documentos por ejecución (presupuesto de la tarea o"
        " ai_max_documents_per_run)."
    ),
}


def _log_ai(ctx: JobContext, outcome: ContextOutcome) -> None:
    """Recuento de la clasificación y de las descripciones con IA, y por qué paró cada una."""
    if outcome.ai is not None:
        # La IA solo recibe lo que las reglas no clasificaron (y, con `missing_axes`, lo que tiene algún eje de etiqueta
        # vacío): sin el total, «24 enviados» de 213 parecía un fallo.
        which = (
            "los que las reglas no clasificaron o tenían vacío algún eje de etiqueta"
            if outcome.ai.get("scope") == "missing_axes"
            else "los que las reglas no clasificaron"
        )
        ctx.log(
            f"IA: {outcome.ai['calls']} de {len(outcome.documents)} documentos enviados ({which}); "
            f"{outcome.ai['classified']} clasificados, {outcome.ai['failed']} con error."
        )
        if outcome.ai.get("cached"):  # doc_organize 2.0: caché de resultados de IA, sin llamar al modelo
            ctx.log(f"IA: {outcome.ai['cached']} documentos resueltos con la caché de IA, sin llamar al modelo.")
        if outcome.ai["stopped"]:
            ctx.log(AI_STOPPED[outcome.ai["stopped"]], level="warning")
    if outcome.enrichment is not None:
        ctx.log(
            f"IA (descripciones): {outcome.enrichment['calls']} documentos enviados (los clasificados sin descripción "
            f"o sin palabras clave); {outcome.enrichment['applied']} completados, {outcome.enrichment['failed']} con "
            "error."
        )
        if outcome.enrichment["stopped"]:
            ctx.log(ENRICHMENT_STOPPED[outcome.enrichment["stopped"]], level="warning")


def run_build(ctx: JobContext, params: ContextBuildParams, project: Project | None) -> ContextBuildResult:
    """Construye el contexto y devuelve sus recuentos."""
    project = require_project(project)
    require_rw(project.destination_location)
    output, request_folders, namer = context_folders(ctx, project)
    semantic = project.context_semantic
    ai = ai_connection(ctx, "litellm") if context_ai_tasks(params) else None
    if ai is None and semantic:  # W6 (G4): la semántica usa la tarea ``embed`` de «Modelos de IA»
        try:
            with ctx.session_factory() as db:
                ai = ai_settings.connection(db, ctx.settings, "litellm")
        except AiNotConfiguredError:
            semantic = False
            ctx.log(
                "La clasificación semántica está activada en el proyecto, pero «Modelos de IA» no está configurado: "
                "se construye sin ella.",
                level="warning",
            )
    if ai is not None:  # redacción por proyecto (D7: por defecto, sí)
        ai = replace(ai, redact_credentials=project.ai_redact_credentials)
    folder_name = params.output_folder_name or "organizado"
    existing = _existing_folder(output, project)
    if existing and existing != folder_name:
        # context.json manda (la proyección pudo perderse): la copia nunca queda repartida entre dos carpetas.
        ctx.log(f"El contexto ya usa la carpeta «{existing}»: se reconstruye en ella.", level="warning")
        folder_name = existing
    request = ContextRequest(
        name=project.name,
        created_at=project.created_at,
        output_root=output,
        folders=request_folders,
        output_folder_name=folder_name,
        candidate_domains=params.domains if params.catalog == "domains" else None,
        manifest_markdown=params.template_markdown if params.catalog in ("template", "manifest") else None,
        template_name=params.template_name,
        threshold=params.threshold,
        build_site=params.build_site,
        site_timeout=float(ctx.settings.context_site_timeout_seconds),
        ai=ai,
        ai_scope=params.ai_scope if params.ai_classification else "off",
        enrich=params.ai_enrichment,
        versions=project.context_versions,
        version_across_extensions=project.context_versions_across_extensions,
        redact_credentials=project.ai_redact_credentials,
        semantic=semantic,
        semantic_threshold=project.context_semantic_threshold,
    )

    def on_progress(phase: str, processed: int, total: int | None, current: str | None) -> None:
        ctx.progress(phase, processed, total, namer.display(current) if current else None)

    ctx.check_cancelled()
    try:
        # Clasificar se cancela entre documentos; copiar, el sitio y guardar no se cortan a medias (fase crítica).
        outcome = library.context.build_context(
            request, on_progress=on_progress, is_cancelled=lambda: ctx.cancelled, critical=ctx.uninterruptible
        )
    except library.context.TemplateInvalidError as exc:
        raise JobFailed(
            "template_invalid", f"La plantilla o el manifiesto no son válidos: {namer.text(str(exc))}"
        ) from None
    except library.DocOrganizeOperationError as exc:
        raise JobFailed("context_failed", str(exc)) from None
    if outcome is None:
        raise JobCancelled()

    for path, error in outcome.failed[:MAX_FAILED_SHOWN]:
        ctx.log(f"No se pudo copiar «{namer.display(path)}»: {namer.text(error)}", level="warning")
    _log_site(ctx, outcome, namer)
    _log_ai(ctx, outcome)
    if outcome.semantic is not None:
        ctx.log(
            f"Semántica: {outcome.semantic['assigned']} documentos con algún eje asignado por similitud; "
            f"{outcome.semantic['embedded']} textos embebidos y {outcome.semantic['cached']} sacados del índice."
        )
    ctx.progress("context_save", 0, None)
    _project_rows(ctx, project, params, outcome, namer)
    refresh_freshness(ctx, project)  # recién construido: al día, salvo lo que no tenga huella (``unknown``)
    result = ContextBuildResult(
        output_folder_name=outcome.output_folder_name,
        domains=len(outcome.domains),
        documents=sum(1 for d in outcome.documents if d.domain_slug is not None),
        unclassified=sum(1 for d in outcome.documents if d.domain_slug is None),
        failed=len(outcome.failed),
        failed_paths=[namer.display(path) for path, _ in outcome.failed[:MAX_FAILED_SHOWN]],
        missing_originals=outcome.missing,
        site_built=outcome.site_built,
        ai=AiPhaseResult.model_validate(
            {"enabled": True, **outcome.ai} if outcome.ai is not None else {"enabled": False}
        ),
        ai_enrichment=AiPhaseResult.model_validate(
            {"enabled": True, **outcome.enrichment} if outcome.enrichment is not None else {"enabled": False}
        ),
        semantic=SemanticResult.model_validate(outcome.semantic or {"enabled": False}),
    )
    with ctx.session_factory() as db:
        audit.record(
            db,
            action=AuditAction.PROJECT_CONTEXT_BUILD,
            ctx=WORKER_CONTEXT,
            actor_id=ctx.created_by,
            target_type="project",
            target_id=project.id,
            details={k: v for k, v in result.stored().items() if k != "failed_paths"} | {"run_id": ctx.run_id},
        )
        db.commit()
    ctx.progress("done", 1, 1)
    return result


def _log_site(ctx: JobContext, outcome: ContextOutcome, namer: DocumentNamer) -> None:
    """Avisos del sitio: por qué no se construyó (la causa en una línea) y qué páginas quedaron fuera del buscador."""
    if outcome.site_error:
        ctx.log(f"El sitio no se pudo construir: {namer.text(outcome.site_error)}", level="warning")
    if outcome.site_search_excluded:
        pages = ", ".join(f"«{page}»" for page in outcome.site_search_excluded[:MAX_FAILED_SHOWN])
        ctx.log(
            f"{len(outcome.site_search_excluded)} página(s) del sitio no aparecen en el buscador por su tamaño "
            f"(se pueden navegar): {pages}",
            level="warning",
        )


def _existing_folder(output: Path, project: Project) -> str | None:
    """Carpeta reorganizada de ``context.json``, o ``None``. doc_organize la valida al leer (G32): uno no válido o
    dañado cuenta como sin contexto."""
    return library.context.existing_folder_name(output, name=project.name, created_at=project.created_at)


def _measure_context(ctx: JobContext, output: Path, folder_name: str | None) -> TreeSize:
    files = size = 0
    for path in library.context.context_paths(output, folder_name):
        if path.is_symlink():
            files += 1
        elif path.is_dir():
            tree = measure(path, ctx, "measure_context")
            files, size = files + tree.files, size + tree.bytes
        elif path.is_file():
            files, size = files + 1, size + path.stat().st_size
    return TreeSize(files=files, bytes=size)


def run_delete(ctx: JobContext, params: ContextDeleteParams, project: Project | None) -> ContextDeleteResult:
    """Cuenta (``dry_run``) o borra el contexto del proyecto."""
    project = require_project(project)
    paths = project_paths(project, ctx)
    output = paths.output.absolute
    folder_name = _existing_folder(output, project)
    if folder_name is None:
        with ctx.session_factory() as db:
            stored = db.get(ProjectContext, project.id)
            folder_name = stored.output_folder_name if stored else None
    size = _measure_context(ctx, output, folder_name)
    result = ContextDeleteResult(output_folder_name=folder_name, files=size.files, bytes=size.bytes)
    if params.dry_run:
        return result
    require_rw(project.destination_location)
    # Solo se borra la carpeta que mostró la vista previa confirmada (la API comprobó que es de esta operación).
    with ctx.session_factory() as db:
        preview = db.get(Run, params.preview_run_id) if params.preview_run_id else None
        shown = parse_result_as(ContextDeleteResult, preview.result, run_id=preview.id) if preview else None
        expected = shown.output_folder_name if shown else None
    if expected != folder_name:
        raise JobFailed("context_changed", "El contexto ha cambiado desde la vista previa: vuelve a lanzarla.")
    ctx.check_cancelled()
    ctx.progress("context_delete", 0, None)
    with ctx.uninterruptible():
        try:
            library.context.delete_context(
                output, name=project.name, created_at=project.created_at, expected_folder=folder_name
            )
        except library.context.ContextFolderInvalidError:
            raise JobFailed(
                "context_changed", "El contexto ha cambiado desde la vista previa: vuelve a lanzarla."
            ) from None
        except library.DocOrganizeOperationError as exc:
            raise JobFailed("context_delete_failed", str(exc)) from None
        with ctx.session_factory() as db:
            db.execute(delete(ContextReviewItem).where(ContextReviewItem.project_id == project.id))
            db.execute(delete(ContextDocumentAxisValue).where(ContextDocumentAxisValue.project_id == project.id))
            db.execute(delete(ContextDocument).where(ContextDocument.project_id == project.id))
            db.execute(delete(ProjectContext).where(ProjectContext.project_id == project.id))
            audit.record(
                db,
                action=AuditAction.PROJECT_CONTEXT_DELETE,
                ctx=WORKER_CONTEXT,
                actor_id=ctx.created_by,
                target_type="project",
                target_id=project.id,
                details={"run_id": ctx.run_id, **result.stored()},
            )
            db.commit()
    ctx.progress("context_delete", 1, 1)
    return result
