"""``context_build`` y ``context_delete``: contexto del proyecto con doc_organize 0.13.0 (WB-7.2, WB-7.3; L-8).

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

from pathlib import Path, PurePosixPath
from typing import Any, Final

from sqlalchemy import delete, insert

from app.db.models import ContextDocument, Project, ProjectContext, Run, utcnow
from app.domain.ai import settings as ai_settings
from app.domain.ai.errors import AiNotConfiguredError
from app.domain.documents.paths import DocumentNamer
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction
from app.domain.runs.operations import ContextBuildParams, ContextDeleteParams, context_ai_family
from app.domain.scan.state import folder_cache
from app.integrations import doc_organize as library
from app.integrations.doc_organize.ai import AiConnection, FamilyKey
from app.integrations.doc_organize.context import ContextDoc, ContextOutcome, ContextRequest, SourceFolder
from app.jobs.context import JobCancelled, JobContext, JobFailed
from app.jobs.operations._files import TreeSize, measure, project_paths, require_rw, source_folders
from app.jobs.operations.common import WORKER_CONTEXT, require_project

#: Documentos fallidos que se guardan en el resultado del run (el total va en ``failed``).
MAX_FAILED_SHOWN: Final = 100
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
        "collision": doc.collision,
        "classified_by": doc.classified_by if doc.domain_slug is not None else None,
    }


def _project_rows(
    ctx: JobContext, project: Project, params: ContextBuildParams, outcome: ContextOutcome, namer: DocumentNamer
) -> None:
    """Sustituye la proyección del contexto del proyecto por la de ``outcome`` en una transacción.

    Las filas se preparan antes de abrirla y se insertan con ``executemany`` por lotes: con 100 000 documentos la
    escritura en ``config.db`` dura poco y no bloquea al resto (eventos de otros runs, sesiones).
    """
    rows = [_row(project.id, seq, doc, namer) for seq, doc in enumerate(outcome.documents)]
    with ctx.session_factory() as db:
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
                collisions_count=outcome.collisions,
                site_built=outcome.site_built,
                ai_classification=params.ai_classification,
                domains=outcome.domains,
                built_by_run_id=ctx.run_id,
                built_at=utcnow(),
            )
        )
        db.flush()
        for start in range(0, len(rows), BATCH):
            db.execute(insert(ContextDocument), rows[start : start + BATCH])
        db.commit()


def context_folders(ctx: JobContext, project: Project) -> tuple[Path, list[SourceFolder], DocumentNamer]:
    """Carpeta del proyecto en el destino, carpetas de origen con su caché y conversiones, y el nombrador de rutas."""
    paths = project_paths(project, ctx)
    output = paths.output.absolute
    folders = source_folders(ctx, project)
    namer = DocumentNamer([(subpath, [root]) for subpath, root in folders], project.source_location.name)
    return (
        output,
        [
            SourceFolder(
                folder=subpath,
                root=root,
                cache_db=folder_cache(paths.state, subpath),
                conversion_dir=library.conversion_dir(output, paths.state, subpath),
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
    "budget": "Se llegó al máximo de documentos con IA por ejecución (ajuste ai_max_documents_per_run).",
}


def run_build(ctx: JobContext, params: ContextBuildParams, project: Project | None) -> dict[str, Any]:
    """Construye el contexto y devuelve sus recuentos."""
    project = require_project(project)
    require_rw(project.destination_location)
    output, request_folders, namer = context_folders(ctx, project)
    ai = ai_connection(ctx, context_ai_family(params)) if params.ai_classification else None
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
    if outcome.collisions:
        ctx.log(
            f"{outcome.collisions} documentos comparten nombre con otro del mismo dominio y tipo: en la carpeta "
            "reorganizada solo queda uno de cada nombre (G30).",
            level="warning",
        )
    if outcome.site_error:
        ctx.log(f"El sitio no se pudo construir: {namer.text(outcome.site_error)}", level="warning")
    if outcome.ai is not None:
        ctx.log(
            f"IA: {outcome.ai['calls']} documentos enviados, {outcome.ai['classified']} clasificados, "
            f"{outcome.ai['failed']} con error."
        )
        if outcome.ai["stopped"]:
            ctx.log(AI_STOPPED[outcome.ai["stopped"]], level="warning")
    ctx.progress("context_save", 0, None)
    _project_rows(ctx, project, params, outcome, namer)
    result: dict[str, Any] = {
        "output_folder_name": outcome.output_folder_name,
        "domains": len(outcome.domains),
        "documents": sum(1 for d in outcome.documents if d.domain_slug is not None),
        "unclassified": sum(1 for d in outcome.documents if d.domain_slug is None),
        "failed": len(outcome.failed),
        "failed_paths": [namer.display(path) for path, _ in outcome.failed[:MAX_FAILED_SHOWN]],
        "collisions": outcome.collisions,
        "missing_originals": outcome.missing,
        "site_built": outcome.site_built,
        "ai": {"enabled": True, **outcome.ai} if outcome.ai is not None else {"enabled": False},
    }
    with ctx.session_factory() as db:
        audit.record(
            db,
            action=AuditAction.PROJECT_CONTEXT_BUILD,
            ctx=WORKER_CONTEXT,
            actor_id=ctx.created_by,
            target_type="project",
            target_id=project.id,
            details={k: v for k, v in result.items() if k != "failed_paths"} | {"run_id": ctx.run_id},
        )
        db.commit()
    ctx.progress("done", 1, 1)
    return result


def _existing_folder(output: Path, project: Project) -> str | None:
    """Carpeta reorganizada de ``context.json`` (validada: el fichero se puede cambiar desde el recurso, G32).

    Raises:
        JobFailed: ``context_folder_invalid`` si no es una carpeta válida del proyecto.
    """
    try:
        return library.context.existing_folder_name(output, name=project.name, created_at=project.created_at)
    except library.context.ContextFolderInvalidError:
        raise JobFailed(
            "context_folder_invalid",
            "context.json indica una carpeta reorganizada no válida; no se toca nada. Revisa la carpeta del proyecto.",
        ) from None


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


def run_delete(ctx: JobContext, params: ContextDeleteParams, project: Project | None) -> dict[str, Any]:
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
    result: dict[str, Any] = {
        "output_folder_name": folder_name,
        "files": size.files,
        "bytes": size.bytes,
    }
    if params.dry_run:
        return result
    require_rw(project.destination_location)
    # Solo se borra la carpeta que mostró la vista previa confirmada (la API comprobó que es de esta operación).
    with ctx.session_factory() as db:
        preview = db.get(Run, params.preview_run_id) if params.preview_run_id else None
        expected = (preview.result or {}).get("output_folder_name") if preview else None
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
            db.execute(delete(ContextDocument).where(ContextDocument.project_id == project.id))
            db.execute(delete(ProjectContext).where(ProjectContext.project_id == project.id))
            audit.record(
                db,
                action=AuditAction.PROJECT_CONTEXT_DELETE,
                ctx=WORKER_CONTEXT,
                actor_id=ctx.created_by,
                target_type="project",
                target_id=project.id,
                details={"run_id": ctx.run_id, **result},
            )
            db.commit()
    ctx.progress("context_delete", 1, 1)
    return result
