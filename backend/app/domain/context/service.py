"""Contexto del proyecto (WB-7.2): resumen y documentos (proyección en ``config.db``, decisión C3), manifiesto de
taxonomía y validación de ``context_build`` al encolar.

Construir y borrar son runs (``context_build``, ``context_delete``); la API solo lee la proyección y, para el
manifiesto, un fichero pequeño del destino a través del resolvedor de ubicaciones.
"""

from __future__ import annotations

import json
import logging
import os
import stat
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final, Literal

from sqlalchemy import ColumnElement, Text, cast, delete, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import (
    ACTIVE_RUN_STATUSES,
    ContextDocument,
    ManifestVersionAction,
    Project,
    ProjectContext,
    ProjectManifestVersion,
    Run,
    User,
)
from app.domain.ai import settings as ai_settings
from app.domain.context import manifest_versions, templates
from app.domain.context.errors import (
    ContextNotFoundError,
    DestinationReadOnlyError,
    InvalidContextBuildError,
    ManifestChangedError,
    ManifestEtagRequiredError,
    ManifestNotFoundError,
    ManifestReplacedError,
    ManifestVersionInvalidError,
    TemplateInvalidError,
    TemplateNotFoundError,
)
from app.domain.documents.errors import OutputNotFoundError, OutputTooLargeError
from app.domain.documents.service import project_namer, read_inside
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction, RequestContext
from app.domain.listing import ListQuery, apply_search, apply_sort
from app.domain.locations.errors import FolderNotFoundError, LocationUnavailableError
from app.domain.locations.paths import resolve_within, run_with_timeout
from app.domain.runs.errors import WriteLockedError
from app.domain.runs.operations import MAX_TEMPLATE_BYTES, ContextBuildParams, context_ai_tasks
from app.integrations.doc_organize import DocOrganizeOperationError
from app.integrations.doc_organize import context as library

logger = logging.getLogger(__name__)

DEFAULT_FOLDER_NAME: Final = "organizado"
#: Tamaño máximo del manifiesto que se copia en una versión (uno mayor que ``MAX_TEMPLATE_BYTES`` solo puede venir de
#: una edición fuera de la app; si pasa también de este, la versión se guarda sin texto y se avisa en el log).
MAX_VERSION_BYTES: Final = 4 * 1024 * 1024
#: ``etag`` de un manifiesto que no se puede leer entero (más grande que ``MAX_VERSION_BYTES``).
TOO_LARGE_ETAG: Final = "too_large"
#: Tamaño máximo del historial del contexto que lee la API (más grande: «Historial del contexto (Excel)»).
MAX_HISTORY_BYTES: Final = 16 * 1024 * 1024
DocumentFilter = Literal["failed", "collision", "ai_disagrees"]


@dataclass(frozen=True)
class Manifest:
    """``taxonomy_manifest.md`` del proyecto (``markdown`` nulo si no existe) y su catálogo si es válido."""

    markdown: str | None
    info: library.TemplateInfo | None = None
    error: str | None = None
    #: Para ``If-Match`` al guardar, borrar o restaurar (``manifest_versions.manifest_etag``).
    etag: str = manifest_versions.NO_MANIFEST_ETAG


# --- lectura de la proyección ----------------------------------------------------------------------------------------


def get_context(db: Session, project: Project) -> ProjectContext:
    """Raises: ContextNotFoundError si el proyecto no tiene contexto construido."""
    context = db.get(ProjectContext, project.id)
    if context is None:
        raise ContextNotFoundError("El proyecto no tiene contexto: constrúyelo primero.")
    return context


def _keywords_contain(keyword: str) -> ColumnElement[bool]:
    """Alguna palabra clave contiene ``keyword``, sobre el texto JSON de la lista.

    El término se escapa igual que lo guarda ``JSON`` (``json.dumps``, con ``\\uXXXX`` fuera de ASCII) para que las tildes
    coincidan; sin distinguir mayúsculas solo en ASCII, como el resto de búsquedas sobre SQLite.
    """
    escaped = json.dumps(keyword.strip().lower())[1:-1]
    return func.lower(cast(ContextDocument.keywords, Text)).contains(escaped, autoescape=True)


def list_documents(
    db: Session,
    project: Project,
    *,
    domain: str | None,
    only: DocumentFilter | None = None,
    language: str | None = None,
    keyword: str | None = None,
    limit: int,
    offset: int,
    listing: ListQuery | None = None,
) -> tuple[list[ContextDocument], int]:
    """Documentos de un dominio (``domain``) o sin clasificar (``None``), en el orden del contexto.

    Filtros 1.5.0: ``language`` (código exacto), ``keyword`` (alguna palabra clave lo contiene) y ``only="ai_disagrees"``
    (la IA propuso un dominio distinto del asignado). La búsqueda ``q`` mira también el autor y la descripción.

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
    elif only == "ai_disagrees":
        where.append(ContextDocument.ai_domain.is_not(None))
        where.append(
            or_(ContextDocument.domain_slug.is_(None), ContextDocument.ai_domain != ContextDocument.domain_slug)
        )
    if language:
        where.append(ContextDocument.language == language.strip().lower())
    if keyword and keyword.strip():
        where.append(_keywords_contain(keyword))
    listing = listing or ListQuery()
    query = apply_search(
        select(ContextDocument).where(*where),
        listing.q,
        [
            ContextDocument.title,
            ContextDocument.path,
            ContextDocument.document_type,
            ContextDocument.organized_path,
            ContextDocument.author,
            ContextDocument.description,
        ],
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


def _read_text(path: Path, root: Path, max_bytes: int) -> str | None:
    """Texto de ``taxonomy_manifest.md`` (``None`` si no existe), leído dentro de ``root`` sin seguir enlaces.

    Raises:
        ManifestReplacedError: Existe, pero no es un fichero normal.
        OutputTooLargeError: Pasa de ``max_bytes``.
    """
    if not _manifest_state(path):
        return None
    try:
        return read_inside(path, root, max_bytes=max_bytes).decode("utf-8", errors="replace")
    except OutputNotFoundError:
        return None


def _current_for_version(settings: Settings, path: Path, root: Path) -> tuple[str | None, str]:
    """``(texto, etag)`` del manifiesto en el disco para guardarlo como versión (hasta ``MAX_VERSION_BYTES``).

    Uno aún mayor da ``(None, "too_large")``: se puede sustituir, pero su versión queda sin texto.
    """
    try:
        text = run_with_timeout(
            lambda: _read_text(path, root, MAX_VERSION_BYTES), settings.location_probe_timeout_seconds
        )
    except OutputTooLargeError:
        return None, TOO_LARGE_ETAG
    if text is not None:
        text = manifest_versions.normalize(text)  # las versiones se guardan siempre con saltos LF
    return text, manifest_versions.manifest_etag(text)


def read_manifest(settings: Settings, project: Project) -> Manifest:
    """``taxonomy_manifest.md`` del proyecto, validado (un manifiesto inválido se devuelve con su error) y su ``etag``."""
    root = _output_root(settings, project)
    path = library.manifest_file(root)

    try:
        markdown = run_with_timeout(
            lambda: _read_text(path, root, MAX_TEMPLATE_BYTES), settings.location_probe_timeout_seconds
        )
    except OutputTooLargeError:
        _, etag = _current_for_version(settings, path, root)
        return Manifest(markdown=None, error=f"El manifiesto pasa de {MAX_TEMPLATE_BYTES // 1024} KiB.", etag=etag)
    etag = manifest_versions.manifest_etag(markdown)
    if markdown is None:
        return Manifest(markdown=None, etag=etag)
    try:
        return Manifest(markdown=markdown, info=library.parse_template(markdown), etag=etag)
    except library.TemplateInvalidError as exc:
        return Manifest(markdown=markdown, error=str(exc), etag=etag)


@dataclass(frozen=True)
class History:
    """Últimas construcciones del contexto (rutas relativas al origen), cuántas hay y, si no se pudo leer, por qué.

    ``builds`` lleva cada construcción, con sus cambios ya recortados, y cuántos cambios tenía en total.
    """

    builds: list[tuple[library.ContextBuild, int]]
    total: int
    error: str | None = None


def read_history(settings: Settings, project: Project, *, limit: int, max_changes: int) -> History:
    """``historial_contexto/CONTEXT_HISTORY.jsonl`` del proyecto (1.5.0): las ``limit`` construcciones más recientes,
    con como mucho ``max_changes`` cambios cada una y rutas relativas a las carpetas de origen.

    El historial no se borra con el contexto. Se lee como el manifiesto: dentro de la carpeta, sin seguir enlaces y con
    tope de tamaño (si lo pasa, se pide el Excel). Sin carpeta del proyecto o sin fichero, el historial está vacío.

    Raises:
        LocationUnavailableError: El destino no responde.
    """
    try:
        root = _output_root(settings, project)
    except ContextNotFoundError:
        return History(builds=[], total=0)
    path = library.history_file(root)

    def _read() -> str | None:
        try:
            info = os.lstat(path)
        except FileNotFoundError:
            return None
        if not stat.S_ISREG(info.st_mode):
            return None  # enlace o carpeta en su lugar: no se sigue (ni se muestra nada de lo que apunte)
        try:
            return read_inside(path, root, max_bytes=MAX_HISTORY_BYTES).decode("utf-8", errors="replace")
        except OutputNotFoundError:
            return None

    try:
        text = run_with_timeout(_read, settings.location_probe_timeout_seconds)
    except OutputTooLargeError:
        return History(builds=[], total=0, error="history_too_large")
    if text is None:
        return History(builds=[], total=0)
    builds = library.parse_history(text)
    namer = project_namer(settings, project)
    shown = [
        (
            replace(
                build,
                changes=[
                    replace(change, source_path=namer.display(change.source_path))
                    for change in build.changes[:max_changes]
                ],
            ),
            len(build.changes),
        )
        for build in builds[:limit]
    ]
    return History(builds=shown, total=len(builds))


def _check_writable(db: Session, project: Project) -> None:
    if project.destination_location.access != "rw":
        raise DestinationReadOnlyError("La ubicación de destino es de solo lectura.")
    active = select(Run.id).where(
        Run.project_id == project.id, Run.is_write.is_(True), Run.status.in_(ACTIVE_RUN_STATUSES)
    )
    if db.scalar(active.limit(1)) is not None:
        raise WriteLockedError("Espera a que termine la operación de escritura en curso.")


def _mutate_manifest(
    db: Session,
    settings: Settings,
    project: Project,
    *,
    if_match: str | None,
    action: ManifestVersionAction,
    actor: User,
    change: Callable[[Path, Path, bool], bool],
) -> tuple[str | None, ProjectManifestVersion | None]:
    """Sección crítica común a guardar, borrar y restaurar: comprobar ``If-Match``, guardar la versión y cambiar.

    1. Sin ``if_match``: 428. Destino ``rw`` y sin escrituras en curso.
    2. Con el cerrojo del proyecto: se lee lo que hay en el disco y se compara su ``etag`` con ``if_match`` (409 si
       cambió). ``change(path, root, apply=False)`` decide primero, sin escribir, si hay algo que hacer (``False``: nada,
       ni versión ni escritura); ``change(path, root, apply=True)`` hace el cambio.
    3. La versión (lo que había) se guarda y **se confirma antes de escribir** (B3). Si la escritura falla de forma
       definitiva, se retira; si se agota el tiempo (la escritura puede seguir en segundo plano), se conserva: es lo
       que había y restaurarla es inocuo. Así el fichero nunca cambia sin versión.

    Devuelve el texto que había y la versión guardada (``None`` si no hubo cambio).

    Raises:
        ManifestEtagRequiredError: Falta ``If-Match``.
        ManifestChangedError: El manifiesto cambió desde que se leyó.
        DestinationReadOnlyError: El destino es de solo lectura.
        WriteLockedError: Hay una escritura en cola o en marcha en el proyecto.
        ManifestReplacedError: El fichero actual no es un fichero normal.
        LocationUnavailableError: El destino no responde o no se pudo escribir.
    """
    if not if_match:
        raise ManifestEtagRequiredError("Recarga el manifiesto y vuelve a intentarlo.")
    _check_writable(db, project)
    root = _output_root(settings, project)
    path = library.manifest_file(root)
    with manifest_versions.project_lock(project.id):
        current, etag = _current_for_version(settings, path, root)
        if etag != if_match.strip('"'):
            raise ManifestChangedError("Otro usuario lo ha cambiado: recarga para ver su versión.")
        if not run_with_timeout(lambda: change(path, root, False), settings.location_probe_timeout_seconds):
            return current, None
        if etag == TOO_LARGE_ETAG:
            logger.warning("Manifiesto del proyecto %s demasiado grande: su versión se guarda sin texto", project.id)
        version = manifest_versions.add_version(db, project.id, current, action, actor_id=actor.id)
        db.commit()
        version_id = version.id
        try:
            run_with_timeout(lambda: change(path, root, True), settings.location_probe_timeout_seconds)
        except LocationUnavailableError:
            raise  # tiempo agotado: la versión se conserva
        except (DocOrganizeOperationError, library.TemplateInvalidError, ManifestReplacedError, OSError) as exc:
            db.execute(delete(ProjectManifestVersion).where(ProjectManifestVersion.id == version_id))
            db.commit()
            if isinstance(exc, ManifestReplacedError):
                raise
            raise LocationUnavailableError("No se pudo escribir el manifiesto en el destino.") from None
        return current, db.get(ProjectManifestVersion, version_id)


def _write_change(project: Project, markdown: str) -> Callable[[Path, Path, bool], bool]:
    """``change`` de ``_mutate_manifest`` que escribe ``markdown`` (nada si es igual a lo que hay)."""
    target = manifest_versions.normalize(markdown)

    def _change(path: Path, root: Path, apply: bool) -> bool:
        if not apply:
            try:
                on_disk = _read_text(path, root, MAX_VERSION_BYTES)
            except OutputTooLargeError:
                return True
            return on_disk is None or manifest_versions.normalize(on_disk) != target
        _manifest_state(path)
        library.save_manifest(root, markdown, name=project.name, created_at=project.created_at)
        return True

    return _change


def _unlink_manifest(path: Path) -> None:
    """Borra ``taxonomy_manifest.md`` sin seguir enlaces (``os.unlink`` borra el enlace, nunca su destino)."""
    if _manifest_state(path):
        os.unlink(path)


def save_manifest(
    db: Session,
    settings: Settings,
    project: Project,
    markdown: str,
    *,
    if_match: str | None,
    actor: User,
    ctx: RequestContext,
) -> Manifest:
    """Valida y escribe ``taxonomy_manifest.md``, guardando antes como versión lo que había.

    El mismo texto que ya hay no escribe ni guarda versión.

    Raises:
        TemplateInvalidError: El Markdown no es un manifiesto válido.
        ManifestEtagRequiredError, ManifestChangedError: Ver ``_mutate_manifest``.
        DestinationReadOnlyError: El destino es de solo lectura.
        WriteLockedError: Hay una escritura en cola o en marcha en el proyecto.
        ManifestReplacedError: El fichero actual no es un fichero normal.
        LocationUnavailableError: El destino no responde o no se pudo escribir.
    """
    info = templates.validate_markdown(markdown)
    _, version = _mutate_manifest(
        db, settings, project, if_match=if_match, action="save", actor=actor, change=_write_change(project, markdown)
    )
    if version is not None:
        audit.record(
            db,
            action=AuditAction.PROJECT_TAXONOMY_MANIFEST_SAVE,
            ctx=ctx,
            actor_id=actor.id,
            target_type="project",
            target_id=project.id,
            details={
                "domains": len(info.domains),
                "material_types": len(info.material_types),
                "version_id": version.id,
            },
        )
        db.commit()
    return Manifest(markdown=markdown, info=info, etag=manifest_versions.manifest_etag(markdown))


def delete_manifest(
    db: Session, settings: Settings, project: Project, *, if_match: str | None, actor: User, ctx: RequestContext
) -> Manifest:
    """Borra ``taxonomy_manifest.md`` guardando antes su versión (acción ``delete``).

    Raises:
        ManifestNotFoundError: No hay manifiesto.
        ManifestEtagRequiredError, ManifestChangedError, DestinationReadOnlyError, WriteLockedError,
        ManifestReplacedError, LocationUnavailableError: Ver ``_mutate_manifest``.
    """

    def _change(path: Path, root: Path, apply: bool) -> bool:
        del root
        if not apply:
            if not _manifest_state(path):
                raise ManifestNotFoundError("El proyecto no tiene manifiesto de taxonomía.")
            return True
        _unlink_manifest(path)
        return True

    _, version = _mutate_manifest(
        db, settings, project, if_match=if_match, action="delete", actor=actor, change=_change
    )
    if version is None:  # no ocurre: sin fichero, la comprobación ya lanza ``ManifestNotFoundError``
        raise ManifestNotFoundError("El proyecto no tiene manifiesto de taxonomía.")
    audit.record(
        db,
        action=AuditAction.PROJECT_TAXONOMY_MANIFEST_DELETE,
        ctx=ctx,
        actor_id=actor.id,
        target_type="project",
        target_id=project.id,
        details={"version_id": version.id},
    )
    db.commit()
    return Manifest(markdown=None)


def restore_manifest(
    db: Session,
    settings: Settings,
    project: Project,
    version_id: int,
    *,
    if_match: str | None,
    actor: User,
    ctx: RequestContext,
) -> Manifest:
    """Restaura la versión ``version_id`` (una «sin manifiesto» borra el fichero) guardando antes lo que había, para
    que restaurar también se pueda deshacer.

    Raises:
        ManifestVersionNotFoundError: No existe esa versión en el proyecto.
        ManifestVersionInvalidError: La versión no es un manifiesto válido.
        ManifestEtagRequiredError, ManifestChangedError, DestinationReadOnlyError, WriteLockedError,
        ManifestReplacedError, LocationUnavailableError: Ver ``_mutate_manifest``.
    """
    stored = manifest_versions.get_version(db, project.id, version_id)
    markdown = stored.markdown
    info: library.TemplateInfo | None = None
    if markdown is not None:
        try:
            info = templates.validate_markdown(markdown)
        except TemplateInvalidError as exc:
            raise ManifestVersionInvalidError(exc.detail) from None
        change = _write_change(project, markdown)
    else:

        def change(path: Path, root: Path, apply: bool) -> bool:
            del root
            if not apply:
                return _manifest_state(path)  # ya no hay manifiesto: nada que hacer
            _unlink_manifest(path)
            return True

    _, version = _mutate_manifest(
        db, settings, project, if_match=if_match, action="restore", actor=actor, change=change
    )
    audit.record(
        db,
        action=AuditAction.PROJECT_TAXONOMY_MANIFEST_RESTORE,
        ctx=ctx,
        actor_id=actor.id,
        target_type="project",
        target_id=project.id,
        details={
            "restored_version_id": version_id,
            "version_id": version.id if version else None,
            "domains": len(info.domains) if info else None,
        },
    )
    db.commit()
    if markdown is None:
        return Manifest(markdown=None)
    return Manifest(markdown=markdown, info=info, etag=manifest_versions.manifest_etag(markdown))


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
    if context_ai_tasks(params):  # doc_organize 2.0: todas las tareas usan la familia ``litellm``
        ai_settings.require_configured(db, settings, "litellm")
    return params.model_copy(update={"output_folder_name": folder, "template_markdown": markdown})
