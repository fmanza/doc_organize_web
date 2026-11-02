"""Contexto, sitio y plantillas de taxonomía de doc_organize 0.13.0 (WB-7.1, WB-7.2, WB-7.3; L-8, L-8a…L-8c).

Construir y borrar el contexto solo se llama desde el subproceso de un job: importa doc_organize **dentro** de la
función (G15). Las plantillas y el manifiesto (texto pequeño, sin Docling) también los usa la API.

Firmas verificadas en el tag ``v0.13.0``::

    ContextBuilder().build(project, documents: list[ConversionResult], candidate_domains=None, threshold=0.5,
        ai_classification_enabled=False, ..., output_folder_name="organizado", taxonomy_manifest=None,
        taxonomy_template_name=None, *, on_progress=None, cancel_token=None) -> Context   # guarda context.json
    Reorganizer().reorganize(project, context, on_document_copied=None, *, on_document_failed=None) -> Path
    Reorganizer().delete_output(project, context)
    SiteGenerator().generate(project, context, *, build=True, site_dir=None, timeout=None) -> SiteResult
    SiteGenerator().build_site(project, *, timeout=None)        # SiteBuildError
    SiteGenerator().delete_site(project, *, site_dir=None)
    ContextRegistry().load_context/save_context/delete_context(project)
    parse_taxonomy_template(text, *, source=) / render_taxonomy_template(manifest, body="")
    list_builtin_templates() / load_builtin_template(name)       # TaxonomyTemplateError
    load_taxonomy_manifest(project) / save_taxonomy_manifest(project, raw_markdown)

Desde 0.12.1/0.13.0 doc_organize no sigue enlaces simbólicos al copiar (G27): las raíces que recibe salen del
resolvedor de ubicaciones, ya resueltas.
"""

from __future__ import annotations

import asyncio
import os
import stat as stat_mode
import threading
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, Final

from app.integrations.doc_organize.projects import DocOrganizeOperationError

if TYPE_CHECKING:
    from app.integrations.doc_organize.ai import AiConnection

#: Caracteres máximos de un error de doc_organize que se guardan (pueden llevar rutas: el job los limpia).
MAX_ERROR_CHARS: Final = 500
TEMPLATE_SOURCE: Final = "plantilla"
CANCEL_POLL_SECONDS: Final = 1.0


class ContextFolderInvalidError(Exception):
    """``context.json`` del destino tiene una carpeta reorganizada no válida o distinta de la esperada (G32)."""


class TemplateInvalidError(Exception):
    """El Markdown no es una plantilla o manifiesto de taxonomía válido; el mensaje es el de doc_organize."""


@dataclass(frozen=True)
class TemplateInfo:
    """Resumen de una plantilla: catálogo de dominios y tipos de material ``(slug, nombre)``."""

    title: str | None
    description: str | None
    domains: list[tuple[str, str]]
    material_types: list[tuple[str, str]]


@dataclass(frozen=True)
class SourceFolder:
    """Carpeta de origen del proyecto para reunir sus documentos convertidos.

    Attributes:
        folder: Carpeta relativa a la ubicación de origen (``""`` = raíz).
        root: Carpeta real (resuelta) en el contenedor.
        cache_db: ``cache.db`` de la carpeta en el estado del proyecto.
        conversion_dir: Carpeta de sus conversiones (``Conversión/<carpeta>``).
    """

    folder: str
    root: Path
    cache_db: Path
    conversion_dir: Path


@dataclass(frozen=True)
class ContextRequest:
    """Una construcción del contexto.

    Attributes:
        output_root: Carpeta real del proyecto en el destino (``root_path`` de doc_organize).
        candidate_domains: Catálogo propio (un eje), o ``None``.
        manifest_markdown: Plantilla o manifiesto (dos ejes) ya validado en la API, o ``None``.
        template_name: Plantilla de la que viene ``manifest_markdown`` (solo informativo en ``context.json``).
        build_site: Generar y construir el sitio Zensical; si no, se borra el que hubiera.
        site_timeout: Segundos máximos de ``zensical build``.
        ai: Clasificación con IA de lo que las reglas dejan sin clasificar (Fase 8): familia de un eje o de
            taxonomía según haya manifiesto. ``None`` = sin IA.
    """

    name: str
    created_at: datetime
    output_root: Path
    folders: list[SourceFolder]
    output_folder_name: str
    candidate_domains: list[str] | None = None
    manifest_markdown: str | None = None
    template_name: str | None = None
    threshold: float = 0.5
    build_site: bool = True
    site_timeout: float | None = None
    ai: AiConnection | None = None


@dataclass(frozen=True)
class ContextDoc:
    """Documento del contexto: ``source_path`` absoluto (el job lo hace relativo) y copia relativa a ``output_root``."""

    domain_slug: str | None
    title: str
    document_type: str | None
    material_type: str | None
    material_type_name: str | None
    source_path: str
    organized_path: str | None
    failed: bool = False
    collision: bool = False
    classified_by: str | None = None


@dataclass
class ContextOutcome:
    """Resultado de una construcción.

    Attributes:
        domains: ``slug``, ``name``, ``description``, ``status`` y ``documents`` de cada dominio.
        failed: ``(ruta absoluta, error)`` de los documentos que no se pudieron copiar (G27).
        missing: Documentos convertidos de la caché cuyo original ya no está en el origen (no entran).
        site_error: Por qué no se construyó el sitio (puede llevar rutas: el job lo limpia).
        ai: Recuento de la IA (``AiTally.as_dict``), o ``None`` si no se usó.
    """

    output_folder_name: str = ""
    domains: list[dict[str, Any]] = field(default_factory=list)
    documents: list[ContextDoc] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)
    missing: int = 0
    collisions: int = 0
    site_built: bool = False
    site_error: str | None = None
    ai: dict[str, Any] | None = None


# --- plantillas y manifiesto (también en la API) ---------------------------------------------------------------------


def _info(manifest: Any) -> TemplateInfo:
    return TemplateInfo(
        title=manifest.title,
        description=manifest.description,
        domains=[(entry.slug, entry.name) for entry in manifest.domains],
        material_types=[(entry.slug, entry.name) for entry in manifest.material_types],
    )


def parse_template(text: str) -> TemplateInfo:
    """Valida ``text`` (front matter YAML de taxonomía + prosa) con ``parse_taxonomy_template``.

    Raises:
        TemplateInvalidError: No es válido (mensaje de doc_organize, sin rutas: el origen se nombra «plantilla»).
    """
    from doc_organize.context.taxonomy_templates import parse_taxonomy_template
    from doc_organize.core.exceptions import TaxonomyTemplateError

    try:
        return _info(parse_taxonomy_template(text, source=TEMPLATE_SOURCE))
    except TaxonomyTemplateError as exc:
        raise TemplateInvalidError(str(exc)) from None


def builtin_templates() -> dict[str, TemplateInfo]:
    """Plantillas incluidas en doc_organize por nombre (``list_builtin_templates`` + ``load_builtin_template``)."""
    from doc_organize.context.taxonomy_templates import list_builtin_templates, load_builtin_template

    return {summary.name: _info(load_builtin_template(summary.name)) for summary in list_builtin_templates()}


def builtin_template_markdown(name: str) -> str | None:
    """Markdown de la plantilla incluida ``name`` (``render_taxonomy_template``: solo el front matter), o ``None``."""
    from doc_organize.context.taxonomy_templates import load_builtin_template, render_taxonomy_template
    from doc_organize.core.exceptions import TaxonomyTemplateError

    try:
        return str(render_taxonomy_template(load_builtin_template(name)))
    except TaxonomyTemplateError:
        return None


def manifest_file(output_root: Path) -> Path:
    """``taxonomy_manifest.md`` del proyecto (``ProjectLayout.taxonomy_manifest_file``, L-8b)."""
    from doc_organize import ProjectLayout

    return Path(ProjectLayout(output_root).taxonomy_manifest_file)


def site_dir(output_root: Path) -> Path:
    """Carpeta del sitio construido (``ProjectLayout.site_dir``, L-8b)."""
    from doc_organize import ProjectLayout

    return Path(ProjectLayout(output_root).site_dir)


def context_paths(output_root: Path, output_folder_name: str | None) -> list[Path]:
    """Lo que gestiona el contexto en ``output_root`` (para la vista previa del borrado): ``context.json``,
    ``domains/``, la carpeta reorganizada, ``zensical.toml``, un ``mkdocs.yml`` anterior, ``.cache/`` y ``site/``."""
    from doc_organize import ProjectLayout

    layout = ProjectLayout(output_root)
    paths = [
        layout.context_file,
        layout.domains_dir,
        layout.site_config_file,
        layout.legacy_mkdocs_config_file,
        layout.site_cache_dir,
        layout.site_dir,
    ]
    if output_folder_name:
        paths.append(layout.reorganized_dir(output_folder_name))
    return [Path(p) for p in paths]


def check_folder_name(name: str) -> str | None:
    """Problema de ``name`` como carpeta reorganizada (``validate_output_folder_name``, L-8b), o ``None``."""
    from doc_organize import validate_output_folder_name
    from doc_organize.core.exceptions import InvalidPathError

    try:
        validate_output_folder_name(name)
    except InvalidPathError as exc:
        return str(exc)
    return None


def _project(name: str, output_root: Path, created_at: datetime) -> Any:
    from doc_organize import Project

    return Project(name=name, root_path=str(output_root), created_at=created_at.isoformat())


def save_manifest(output_root: Path, text: str, *, name: str, created_at: datetime) -> TemplateInfo:
    """Valida y escribe ``taxonomy_manifest.md`` (``save_taxonomy_manifest``).

    Raises:
        TemplateInvalidError: El Markdown no es un manifiesto válido.
        DocOrganizeOperationError: No se pudo escribir.
    """
    from doc_organize.context.taxonomy_manifest import save_taxonomy_manifest
    from doc_organize.core.exceptions import DocOrganizeError, TaxonomyManifestError, TaxonomyTemplateError

    info = parse_template(text)
    try:
        clear_temporaries(output_root)
        asyncio.run(save_taxonomy_manifest(_project(name, output_root, created_at), text))
    except (TaxonomyManifestError, TaxonomyTemplateError) as exc:
        raise TemplateInvalidError(str(exc)) from None
    except (DocOrganizeError, OSError) as exc:
        raise DocOrganizeOperationError("No se pudo guardar el manifiesto de taxonomía.") from exc
    return info


# --- construir y borrar (subproceso del job) -------------------------------------------------------------------------


def _is_file(path: str) -> bool:
    try:
        return stat_mode.S_ISREG(os.lstat(path).st_mode)
    except OSError:
        return False


def converted_documents(folders: list[SourceFolder]) -> tuple[list[Any], int]:
    """``ConversionResult`` de los documentos convertidos con éxito cuyo original, ``.md`` y ``.json`` siguen ahí como
    ficheros normales, y cuántos de la caché no (movidos a ``duplicados/``, borrados, sustituidos por enlaces…).

    Mismo criterio que ``_gather_converted_documents`` de la web integrada, por carpeta (una caché y una carpeta de
    conversiones cada una, G18): salidas con ``resolve_output_paths``/``resolve_images_dir``. Se descartan aquí los que
    no están completos: ``Reorganizer`` valida todos antes de copiar y uno solo incompleto pararía la construcción.
    """
    from doc_organize import ConversionResult, ConversionStatus, resolve_images_dir, resolve_output_paths
    from doc_organize.export import load_cache_entries

    documents: list[Any] = []
    missing = 0
    for folder in folders:
        if not folder.cache_db.is_file():
            continue
        entries = asyncio.run(load_cache_entries([folder.cache_db]))
        for entry in entries:
            if entry.conversion_status != ConversionStatus.SUCCESS:
                continue
            if not Path(entry.file_path).is_relative_to(folder.root):
                continue
            markdown, json_path = resolve_output_paths(entry.file_path, folder.conversion_dir, [str(folder.root)])
            if not all(_is_file(str(path)) for path in (entry.file_path, markdown, json_path)):
                missing += 1
                continue
            images = resolve_images_dir(markdown)
            documents.append(
                ConversionResult(
                    source_path=entry.file_path,
                    markdown_path=str(markdown),
                    json_path=str(json_path),
                    images_dir=str(images) if os.path.lexists(images) else None,
                    success=True,
                )
            )
    return documents, missing


def existing_folder_name(output_root: Path, *, name: str, created_at: datetime) -> str | None:
    """``output_folder_name`` del ``context.json`` que haya en ``output_root`` (o ``None``).

    ``context.json`` vive en el destino y se puede cambiar fuera de la app: doc_organize no valida ese campo al leerlo
    (G32) y lo usa para copiar y borrar. Se valida aquí.

    Raises:
        ContextFolderInvalidError: El nombre guardado no es una carpeta válida del proyecto.
    """
    from doc_organize import ContextRegistry
    from doc_organize.core.exceptions import ContextError

    try:
        context = asyncio.run(ContextRegistry().load_context(_project(name, output_root, created_at)))
    except (ContextError, OSError, ValueError):
        return None
    folder = str(context.output_folder_name)
    if check_folder_name(folder) is not None:
        raise ContextFolderInvalidError()
    return folder


#: Temporales de las escrituras «atómicas» de doc_organize 0.13.0, que no usan ``O_NOFOLLOW`` (G31).
_ROOT_TEMPORARIES: Final = ("taxonomy_manifest.tmp", "context.tmp", "zensical.toml.tmp")
_DOMAIN_TEMPORARIES: Final = ("DOMAIN.tmp", "index.tmp")


def clear_temporaries(output_root: Path, output_folder_name: str | None = None) -> int:
    """Quita los temporales de doc_organize que no sean ficheros normales (p. ej. un enlace puesto desde el recurso de
    red): doc_organize escribiría a través de ellos (G31). Devuelve cuántos ha quitado (el enlace, nunca su destino).

    Reduce la ventana, no la cierra: el arreglo es que doc_organize cree el temporal con ``O_EXCL | O_NOFOLLOW``.
    """
    from doc_organize import ProjectLayout

    layout = ProjectLayout(output_root)
    candidates = [output_root / name for name in _ROOT_TEMPORARIES]
    if output_folder_name:
        candidates.append(Path(layout.reorganized_dir(output_folder_name)) / "index.md.tmp")
    domains = Path(layout.domains_dir)
    if os.path.isdir(domains) and not os.path.islink(domains):
        for entry in os.scandir(domains):
            if entry.is_dir(follow_symlinks=False):
                candidates.extend(Path(entry.path) / name for name in _DOMAIN_TEMPORARIES)
    removed = 0
    for path in candidates:
        if os.path.lexists(path) and not _is_file(str(path)):
            try:
                os.unlink(path)
            except OSError:
                raise DocOrganizeOperationError("Un temporal del contexto no es un fichero normal.") from None
            removed += 1
    return removed


def _organized(document: Any, output_folder_name: str, slug: str) -> str:
    from doc_organize.context.reorganizer import resolve_document_slug_parts

    kind, stem = resolve_document_slug_parts(document)
    return PurePosixPath(output_folder_name, slug, kind, stem, Path(document.source_path).name).as_posix()


def _outcome(context: Any, failed: list[tuple[str, str]], missing: int) -> ContextOutcome:
    failed_paths = {path for path, _ in failed}
    docs: list[ContextDoc] = []
    domains: list[dict[str, Any]] = []
    seen: dict[str, int] = {}
    for domain in context.domains:
        domains.append(
            {
                "slug": domain.slug,
                "name": domain.name,
                "description": domain.description,
                "status": str(domain.status.value),
                "documents": len(domain.documents),
            }
        )
        for document in domain.documents:
            organized = _organized(document, context.output_folder_name, domain.slug)
            # Sin distinguir mayúsculas: en SMB «Acta» y «acta» son la misma carpeta.
            target = str(PurePosixPath(organized).parent).casefold()
            seen[target] = seen.get(target, 0) + 1
            docs.append(
                ContextDoc(
                    domain_slug=domain.slug,
                    title=document.title,
                    document_type=document.document_type,
                    material_type=document.material_type,
                    material_type_name=document.material_type_name,
                    source_path=document.source_path,
                    organized_path=None if document.source_path in failed_paths else organized,
                    failed=document.source_path in failed_paths,
                    classified_by=str(document.classified_by) if document.classified_by else None,
                )
            )
    # G30: dos documentos con la misma carpeta de destino (mismo dominio, tipo y ``stem``) se sobrescriben.
    collided = {target for target, count in seen.items() if count > 1}
    docs = [
        replace(d, collision=True)
        if d.organized_path and str(PurePosixPath(d.organized_path).parent).casefold() in collided
        else d
        for d in docs
    ]
    docs.extend(
        ContextDoc(
            domain_slug=None,
            title=Path(path).name,
            document_type=Path(path).suffix.lstrip(".").lower() or None,
            material_type=None,
            material_type_name=None,
            source_path=path,
            organized_path=None,
        )
        for path in context.unclassified_documents
    )
    return ContextOutcome(
        output_folder_name=context.output_folder_name,
        domains=domains,
        documents=docs,
        failed=failed,
        missing=missing,
        collisions=sum(1 for d in docs if d.collision),
        site_built=bool(context.site_built),
    )


def build_context(
    request: ContextRequest,
    *,
    on_progress: Callable[[str, int, int | None, str | None], None],
    is_cancelled: Callable[[], bool],
    critical: Callable[[], AbstractContextManager[None]],
) -> ContextOutcome | None:
    """Clasifica, reorganiza y (si se pide) construye el sitio; guarda ``context.json``.

    La clasificación se cancela entre documentos con el ``CancelToken`` de doc_organize (L-2), antes de guardar nada
    (``None``). Copiar, construir el sitio y guardar van dentro de ``critical()`` (el worker no corta el subproceso):
    ``Reorganizer`` y ``zensical build`` no tienen punto de parada.

    Raises:
        TemplateInvalidError: El manifiesto no es válido.
        DocOrganizeOperationError: doc_organize no pudo clasificar, copiar o guardar (mensaje genérico).
    """
    from doc_organize import (
        CancelToken,
        ContextBuilder,
        ContextRegistry,
        Reorganizer,
        SiteBuildError,
        SiteGenerator,
        parse_taxonomy_template,
    )
    from doc_organize.core.exceptions import DocOrganizeError, OperationCancelledError, TaxonomyTemplateError

    from app.integrations.doc_organize.ai import AiTally, classification_client

    if request.ai is not None:
        expected = (
            "litellm_taxonomy_classification" if request.manifest_markdown is not None else "litellm_classification"
        )
        if request.ai.family != expected:
            raise ValueError(f"La clasificación con IA de este catálogo usa {expected}")
    if is_cancelled():
        return None
    on_progress("context_gather", 0, None, None)
    documents, missing = converted_documents(request.folders)
    manifest = None
    if request.manifest_markdown is not None:
        try:
            manifest = parse_taxonomy_template(request.manifest_markdown, source=TEMPLATE_SOURCE)
        except TaxonomyTemplateError as exc:
            raise TemplateInvalidError(str(exc)) from None
    project = _project(request.name, request.output_root, request.created_at)
    failed: list[tuple[str, str]] = []
    token = CancelToken()
    stop = threading.Event()

    def _bridge() -> None:  # une la cancelación del job (BD) con el CancelToken de la librería (G2)
        while True:
            if is_cancelled():
                token.cancel()
                return
            if stop.wait(CANCEL_POLL_SECONDS):
                return

    async def _copied(index: int, total: int, path: str) -> None:
        on_progress("context_reorganize", index, total, path)

    async def _failed(index: int, total: int, path: str, error: str) -> None:
        failed.append((path, error[:MAX_ERROR_CHARS]))
        on_progress("context_reorganize", index, total, path)

    tally: AiTally | None = None

    def _classified(event: Any) -> None:  # progreso de la Sub-fase B (un documento enviado a la IA)
        on_progress("context_ai", int(event.processed), int(event.total) if event.total else None, None)

    async def _classify() -> Any:
        nonlocal tally
        kwargs: dict[str, Any] = {
            "candidate_domains": request.candidate_domains or None,
            "threshold": request.threshold,
            "output_folder_name": request.output_folder_name,
            "taxonomy_manifest": manifest,
            "taxonomy_template_name": request.template_name if manifest is not None else None,
            "cancel_token": token,
        }
        if request.ai is None:
            return await ContextBuilder().build(project, documents, **kwargs)
        tally = AiTally()
        async with classification_client(request.ai, tally) as client:
            client_arg = "taxonomy_classification_client" if manifest is not None else "ai_classification_client"
            kwargs[client_arg] = client
            return await ContextBuilder().build(
                project, documents, ai_classification_enabled=True, on_progress=_classified, **kwargs
            )

    async def _run() -> ContextOutcome | None:
        on_progress("context_classify", 0, len(documents), None)
        if is_cancelled():  # sin esperar al hilo: el primer punto de parada de doc_organize es al empezar
            token.cancel()
        try:
            context = await _classify()
        except OperationCancelledError:
            return None
        on_progress("context_classify", len(documents), len(documents), None)
        with critical():
            total = sum(len(domain.documents) for domain in context.domains)
            on_progress("context_reorganize", 0, total, None)
            await Reorganizer().reorganize(project, context, on_document_copied=_copied, on_document_failed=_failed)
            context.reorganized = True
            site_error: str | None = None
            generator = SiteGenerator()
            if request.build_site:
                on_progress("context_site", 0, None, None)
                clear_temporaries(request.output_root, request.output_folder_name)
                await generator.generate(project, context, build=False)
                context.site_generated = True
                try:
                    await generator.build_site(project, timeout=request.site_timeout)
                except SiteBuildError as exc:
                    context.site_built = False
                    site_error = str(exc)[:MAX_ERROR_CHARS]
                else:
                    context.site_built = True
            else:
                await generator.delete_site(project)
                context.site_generated = False
                context.site_built = False
            clear_temporaries(request.output_root, request.output_folder_name)
            await ContextRegistry().save_context(project, context)
        outcome = _outcome(context, failed, missing)
        outcome.site_error = site_error
        outcome.ai = tally.as_dict() if tally is not None else None
        return outcome

    clear_temporaries(request.output_root, request.output_folder_name)
    watcher = threading.Thread(target=_bridge, name="dow-context-cancel", daemon=True)
    watcher.start()
    try:
        return asyncio.run(_run())
    except (DocOrganizeError, OSError) as exc:
        raise DocOrganizeOperationError("doc_organize no pudo construir el contexto.") from exc
    finally:
        stop.set()


def delete_context(output_root: Path, *, name: str, created_at: datetime, expected_folder: str | None) -> bool:
    """Borra la carpeta reorganizada, el sitio y ``context.json``/``domains/`` (``False`` si no había ``context.json``).

    ``expected_folder`` es la carpeta de la vista previa confirmada: si ``context.json`` dice otra (o una que no es
    válida, G32), no se borra nada. Sin ``context.json`` se borra la carpeta de la vista previa.

    Raises:
        ContextFolderInvalidError: La carpeta de ``context.json`` no es válida o no es la de la vista previa.
        DocOrganizeOperationError: No se pudo borrar (p. ej. la carpeta reorganizada pasa por un enlace).
    """
    from doc_organize import Context, ContextRegistry, Reorganizer, SiteGenerator
    from doc_organize.core.exceptions import ContextNotFoundError, DocOrganizeError

    project = _project(name, output_root, created_at)

    async def _run() -> bool:
        registry = ContextRegistry()
        try:
            context = await registry.load_context(project)
        except ContextNotFoundError:
            if expected_folder is not None and check_folder_name(expected_folder) is None:
                await Reorganizer().delete_output(
                    project, Context(project_name=name, output_folder_name=expected_folder)
                )
            await SiteGenerator().delete_site(project)
            return False
        folder = str(context.output_folder_name)
        if check_folder_name(folder) is not None or folder != expected_folder:
            raise ContextFolderInvalidError()
        await Reorganizer().delete_output(project, context)
        await SiteGenerator().delete_site(project)
        await registry.delete_context(project)
        return True

    try:
        return asyncio.run(_run())
    except (DocOrganizeError, OSError) as exc:
        raise DocOrganizeOperationError("doc_organize no pudo borrar el contexto.") from exc
