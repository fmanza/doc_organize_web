"""Contexto del proyecto (WB-7.2): resumen y documentos (proyección en ``config.db``, decisión C3), manifiesto de
taxonomía y validación de ``context_build`` al encolar.

Construir y borrar son runs (``context_build``, ``context_delete``); la API solo lee la proyección y, para el
manifiesto, un fichero pequeño del destino a través del resolvedor de ubicaciones.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import ACTIVE_RUN_STATUSES, ContextDocument, Project, ProjectContext, Run, User
from app.domain.ai import settings as ai_settings
from app.domain.context import templates
from app.domain.context.errors import (
    ContextNotFoundError,
    DestinationReadOnlyError,
    InvalidContextBuildError,
    ManifestReplacedError,
    TemplateNotFoundError,
)
from app.domain.documents.errors import OutputNotFoundError, OutputTooLargeError
from app.domain.documents.service import read_inside
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction, RequestContext
from app.domain.listing import ListQuery, apply_search, apply_sort
from app.domain.locations.errors import FolderNotFoundError, LocationUnavailableError
from app.domain.locations.paths import resolve_within, run_with_timeout
from app.domain.runs.errors import WriteLockedError
from app.domain.runs.operations import MAX_TEMPLATE_BYTES, ContextBuildParams, context_ai_family
from app.integrations.doc_organize import DocOrganizeOperationError
from app.integrations.doc_organize import context as library

DEFAULT_FOLDER_NAME: Final = "organizado"
DocumentFilter = Literal["failed", "collision"]


@dataclass(frozen=True)
class Manifest:
    """``taxonomy_manifest.md`` del proyecto (``markdown`` nulo si no existe) y su catálogo si es válido."""

    markdown: str | None
    info: library.TemplateInfo | None = None
    error: str | None = None


# --- lectura de la proyección ----------------------------------------------------------------------------------------


def get_context(db: Session, project: Project) -> ProjectContext:
    """Raises: ContextNotFoundError si el proyecto no tiene contexto construido."""
    context = db.get(ProjectContext, project.id)
    if context is None:
        raise ContextNotFoundError("El proyecto no tiene contexto: constrúyelo primero.")
    return context


def list_documents(
    db: Session,
    project: Project,
    *,
    domain: str | None,
    only: DocumentFilter | None = None,
    limit: int,
    offset: int,
    listing: ListQuery | None = None,
) -> tuple[list[ContextDocument], int]:
    """Documentos de un dominio (``domain``) o sin clasificar (``None``), en el orden del contexto.

    Raises:
        ContextNotFoundError: Sin contexto o sin ese dominio.
    """
    context = get_context(db, project)
    if domain is not None and domain not in {d["slug"] for d in context.domains}:
        raise ContextNotFoundError("Ese dominio no está en el contexto.")
    where = [ContextDocument.project_id == project.id]
    where.append(ContextDocument.domain_slug == domain if domain is not None else ContextDocument.domain_slug.is_(None))
    if only == "failed":
        where.append(ContextDocument.failed.is_(True))
    elif only == "collision":
        where.append(ContextDocument.collision.is_(True))
    listing = listing or ListQuery()
    query = apply_search(
        select(ContextDocument).where(*where),
        listing.q,
        [ContextDocument.title, ContextDocument.path, ContextDocument.document_type, ContextDocument.organized_path],
    )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    columns = {
        "title": func.lower(ContextDocument.title),
        "path": ContextDocument.path,
        "document_type": ContextDocument.document_type,
        "organized_path": ContextDocument.organized_path,
    }
    query = apply_sort(query, listing, columns, default=[ContextDocument.seq], tiebreak=ContextDocument.seq)
    rows = db.scalars(query.limit(limit).offset(offset))
    return list(rows), int(total)


# --- manifiesto de taxonomía -----------------------------------------------------------------------------------------


def _output_root(settings: Settings, project: Project) -> Path:
    """Carpeta real del proyecto en el destino.

    Raises:
        ContextNotFoundError: La carpeta ya no existe.
        LocationUnavailableError: El destino no responde.
    """
    destination = project.destination_location
    try:
        resolved = resolve_within(
            Path(destination.container_path),
            project.destination_subpath,
            timeout=settings.location_probe_timeout_seconds,
        )
    except FolderNotFoundError:
        raise ContextNotFoundError("La carpeta del proyecto ya no existe en el destino.") from None
    return resolved.absolute


def _manifest_state(path: Path) -> bool:
    """Si existe ``taxonomy_manifest.md`` como fichero normal.

    Raises:
        ManifestReplacedError: Existe, pero no es un fichero normal (enlace, carpeta…).
    """
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return False
    if not stat.S_ISREG(info.st_mode):
        raise ManifestReplacedError()
    return True


def read_manifest(settings: Settings, project: Project) -> Manifest:
    """``taxonomy_manifest.md`` del proyecto, validado (un manifiesto inválido se devuelve con su error)."""
    root = _output_root(settings, project)
    path = library.manifest_file(root)

    def _read() -> str | None:
        if not _manifest_state(path):
            return None
        try:
            return read_inside(path, root, max_bytes=MAX_TEMPLATE_BYTES).decode("utf-8", errors="replace")
        except OutputNotFoundError:
            return None

    try:
        markdown = run_with_timeout(_read, settings.location_probe_timeout_seconds)
    except OutputTooLargeError:
        return Manifest(markdown=None, error=f"El manifiesto pasa de {MAX_TEMPLATE_BYTES // 1024} KiB.")
    if markdown is None:
        return Manifest(markdown=None)
    try:
        return Manifest(markdown=markdown, info=library.parse_template(markdown))
    except library.TemplateInvalidError as exc:
        return Manifest(markdown=markdown, error=str(exc))


def _check_writable(db: Session, project: Project) -> None:
    if project.destination_location.access != "rw":
        raise DestinationReadOnlyError("La ubicación de destino es de solo lectura.")
    active = select(Run.id).where(
        Run.project_id == project.id, Run.is_write.is_(True), Run.status.in_(ACTIVE_RUN_STATUSES)
    )
    if db.scalar(active.limit(1)) is not None:
        raise WriteLockedError("Espera a que termine la operación de escritura en curso.")


def save_manifest(
    db: Session, settings: Settings, project: Project, markdown: str, *, actor: User, ctx: RequestContext
) -> Manifest:
    """Valida y escribe ``taxonomy_manifest.md`` en la carpeta del proyecto.

    Raises:
        TemplateInvalidError: El Markdown no es un manifiesto válido.
        DestinationReadOnlyError: El destino es de solo lectura.
        WriteLockedError: Hay una escritura en cola o en marcha en el proyecto.
        ManifestReplacedError: El fichero actual no es un fichero normal.
        LocationUnavailableError: El destino no responde o no se pudo escribir.
    """
    info = templates.validate_markdown(markdown)
    _check_writable(db, project)
    root = _output_root(settings, project)
    path = library.manifest_file(root)

    def _write() -> None:
        _manifest_state(path)
        library.save_manifest(root, markdown, name=project.name, created_at=project.created_at)

    try:
        run_with_timeout(_write, settings.location_probe_timeout_seconds)
    except (DocOrganizeOperationError, library.TemplateInvalidError):
        raise LocationUnavailableError("No se pudo guardar el manifiesto en el destino.") from None
    audit.record(
        db,
        action=AuditAction.PROJECT_TAXONOMY_MANIFEST_SAVE,
        ctx=ctx,
        actor_id=actor.id,
        target_type="project",
        target_id=project.id,
        details={"domains": len(info.domains), "material_types": len(info.material_types)},
    )
    db.commit()
    return Manifest(markdown=markdown, info=info)


# --- validación de context_build al encolar --------------------------------------------------------------------------


def validate_build(
    db: Session, settings: Settings, project: Project, params: ContextBuildParams, *, actor: User
) -> ContextBuildParams:
    """Fija la carpeta reorganizada y la plantilla o manifiesto (Markdown vigente) del run.

    Raises:
        DestinationReadOnlyError: El destino es de solo lectura.
        InvalidContextBuildError: Carpeta no válida o distinta de la del contexto, plantilla inexistente o manifiesto
            ausente o no válido.
        AiNotConfiguredError: Se pide IA y su familia no está configurada.
    """
    if project.destination_location.access != "rw":
        raise DestinationReadOnlyError("La ubicación de destino es de solo lectura.")
    existing = db.get(ProjectContext, project.id)
    folder = params.output_folder_name.strip() if params.output_folder_name else None
    if existing is not None:
        if folder and folder != existing.output_folder_name:
            raise InvalidContextBuildError(
                f"La carpeta del contexto es «{existing.output_folder_name}»: para cambiarla, borra antes el contexto."
            )
        folder = existing.output_folder_name
    folder = folder or DEFAULT_FOLDER_NAME
    problem = library.check_folder_name(folder)
    if problem:
        raise InvalidContextBuildError(f"«{folder}» no sirve como carpeta del contexto: {problem}")

    markdown: str | None = None
    if params.catalog == "template" and params.template_name is not None:
        try:
            markdown = templates.template_markdown(db, actor, params.template_name)
        except TemplateNotFoundError:
            raise InvalidContextBuildError(f"No existe la plantilla «{params.template_name}».") from None
    elif params.catalog == "manifest":
        manifest = read_manifest(settings, project)
        if manifest.markdown is None:
            raise InvalidContextBuildError("El proyecto no tiene manifiesto de taxonomía: guárdalo primero.")
        if manifest.error:
            raise InvalidContextBuildError(f"El manifiesto del proyecto no es válido: {manifest.error}")
        markdown = manifest.markdown
    if params.ai_classification:
        ai_settings.require_configured(db, settings, context_ai_family(params))
    return params.model_copy(update={"output_folder_name": folder, "template_markdown": markdown})
