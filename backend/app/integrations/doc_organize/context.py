"""Contexto, sitio y plantillas de taxonomía de doc_organize (WB-7.1, WB-7.2, WB-7.3; L-8, L-8a…L-8f; 2.0 en W2).

Construir y borrar el contexto solo se llama desde el subproceso de un job: importa doc_organize **dentro** de la
función (G15). Las plantillas y el manifiesto (texto pequeño, sin Docling) también los usa la API.

Firmas verificadas en el tag ``v2.0.0a2``::

    ContextBuilder().build(project, documents: list[ConversionResult], *, candidate_domains=None, threshold=0.5,
        taxonomy_manifest=None, taxonomy_template_name=None, output_folder_name="organizado", llm=None,
        ai_scope="off", enrich=False, prompts=None, ai_cache=True, profile=None, decisions=True, scan_roots=None,
        versions="all", semantic=False, ..., on_progress=None, cancel_token=None, ai_max_failures=None,
        ai_max_documents=None, persist=True) -> Context
    Context.ai_stats (AiStats), Context.model_for_task(task), Context.taxonomy_axes, DomainDocument.classification
    TaxonomyManifest.axes / .folder_axis / .subfolder_axis / .tag_axes  # sin .domains ni .material_types (2.0)
    DomainDocument.organized_path    # .md copiado, relativo a la carpeta reorganizada (L-8d)
    Reorganizer().reorganize(project, context, on_document_copied=None, *, on_document_failed=None) -> Path
    Reorganizer().delete_output(project, context)
    SiteGenerator().generate(project, context, *, build=True, site_dir=None, timeout=None) -> SiteResult
    SiteGenerator().build_site(project, *, timeout=None)        # SiteBuildError
    SiteGenerator().delete_site(project, *, site_dir=None)
    ContextRegistry().load_context/save_context/delete_context(project)   # ContextError si output_folder_name no vale
    parse_taxonomy_template(text, *, source=) / render_taxonomy_template(manifest, body="")
    list_builtin_templates() / load_builtin_template(name)       # TaxonomyTemplateError
    load_taxonomy_manifest(project) / save_taxonomy_manifest(project, raw_markdown)

Desde 0.12.1/0.13.0 doc_organize no sigue enlaces simbólicos al copiar (G27): las raíces que recibe salen del
resolvedor de ubicaciones, ya resueltas. Desde 0.14.0 tampoco se sobrescriben documentos con el mismo nombre (G30),
las escrituras atómicas no siguen enlaces (G31) y ``Context`` valida ``output_folder_name`` al leer ``context.json``
(G32): la web ya no necesita sus rodeos.

Con doc_organize 1.5.0, ``ContextBuilder.build`` lee el ``context.json`` anterior y añade una línea a
``historial_contexto/CONTEXT_HISTORY.jsonl`` en ``output_root``, abre cada original para sus propiedades (autor,
descripción, palabras clave) y clasifica sin distinguir tildes. ``ContextRegistry.load_context`` lanza ``ContextError``
ante cualquier ``context.json`` dañado. Con 2.0 lee también los ``context.json`` y manifiestos de 1.x (los migra en
memoria) y escribe los de 2.0.
"""

from __future__ import annotations

import asyncio
import os
import stat as stat_mode
import threading
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
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
    """La carpeta reorganizada de ``context.json`` no es la de la vista previa confirmada del borrado."""


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
        ai: Conexión de la familia ``litellm`` (doc_organize 2.0, cliente único), o ``None`` = sin IA.
        ai_scope: Qué clasifica la IA (``ContextBuilder.build(ai_scope=)``): ``off``, ``unclassified`` (lo que las
            reglas dejan sin clasificar, la Sub-fase B de 1.x) o ``missing_axes``.
        enrich: Descripción y palabras clave con IA de los documentos que no las declaran (1.5.0, tarea ``enrich``).
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
    ai_scope: str = "off"
    enrich: bool = False


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
    # 1.5.0: propiedades del documento y trazabilidad de la clasificación (``DomainDocument``).
    author: str | None = None
    description: str | None = None
    keywords: list[str] = field(default_factory=list)
    language: str | None = None
    ai_filled: list[str] = field(default_factory=list)
    rules_domain: str | None = None
    rules_confidence: float | None = None
    ai_domain: str | None = None
    ai_confidence: float | None = None
    ai_reasoning: str | None = None
    material_type_confidence: float | None = None
    #: Sin clasificar (1.6.0): ``incomplete_artifacts`` o ``below_threshold``; nulo si está clasificado o el contexto es
    #: anterior a 1.6.0.
    unclassified_reason: str | None = None


@dataclass
class ContextOutcome:
    """Resultado de una construcción.

    Attributes:
        domains: ``slug``, ``name``, ``description``, ``status`` y ``documents`` de cada dominio.
        failed: ``(ruta absoluta, error)`` de los documentos que no se pudieron copiar (G27).
        missing: Documentos convertidos de la caché cuyo original ya no está en el origen (no entran).
        site_error: Por qué no se construyó el sitio, en una línea (``SiteBuildError.cause``; puede llevar rutas: el
            job lo limpia).
        site_search_excluded: Páginas del sitio que doc_organize sacó del buscador porque superan el límite del
            índice de Zensical (rutas relativas a la carpeta reorganizada); se siguen navegando.
        ai: Recuento de la IA (``classification_stats``), o ``None`` si no se usó.
        enrichment: Recuento de las descripciones con IA (``enrichment_stats``, 1.5.0), o ``None`` si no se usó.
        built_with_version: Versión de doc_organize que construyó el contexto (1.5.0).
        ai_classification_model: Modelo de la clasificación con IA, si se ejecutó (1.5.0).
        ai_enrichment_model: Modelo del enriquecimiento con IA, si se ejecutó (1.5.0).
    """

    output_folder_name: str = ""
    domains: list[dict[str, Any]] = field(default_factory=list)
    documents: list[ContextDoc] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)
    missing: int = 0
    site_built: bool = False
    site_error: str | None = None
    site_search_excluded: list[str] = field(default_factory=list)
    ai: dict[str, Any] | None = None
    enrichment: dict[str, Any] | None = None
    built_with_version: str | None = None
    ai_classification_model: str | None = None
    ai_enrichment_model: str | None = None


# --- plantillas y manifiesto (también en la API) ---------------------------------------------------------------------


def _info(manifest: Any) -> TemplateInfo:
    return TemplateInfo(
        title=manifest.title,
        description=manifest.description,
        domains=[(entry.slug, entry.name) for entry in manifest.folder_axis.entries],
        material_types=[(entry.slug, entry.name) for entry in manifest.subfolder_axis.entries],
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
    ``unclassified.json`` (1.6.0), ``domains/``, la carpeta reorganizada, ``zensical.toml``, un ``mkdocs.yml`` anterior,
    ``.cache/`` y ``site/``. El historial (y sus copias giradas) no: se conserva al borrar."""
    from doc_organize import ProjectLayout

    layout = ProjectLayout(output_root)
    paths = [
        layout.context_file,
        layout.unclassified_file,
        layout.domains_dir,
        layout.site_config_file,
        layout.legacy_mkdocs_config_file,
        layout.site_cache_dir,
        layout.site_dir,
    ]
    if output_folder_name:
        paths.append(layout.reorganized_dir(output_folder_name))
    return [Path(p) for p in paths]


def history_file(output_root: Path) -> Path:
    """``historial_contexto/CONTEXT_HISTORY.jsonl`` del proyecto (``ProjectLayout.context_history``, 1.5.0)."""
    from doc_organize import ProjectLayout

    return Path(ProjectLayout(output_root).context_history)


@dataclass(frozen=True)
class ContextChangeRow:
    """Un documento que entró (``added``), salió (``removed``) o cambió de sitio (``reclassified``) en una construcción.

    ``source_path`` es la del contenedor: quien la muestre la hace relativa.
    """

    source_path: str
    change: str
    previous_domain: str | None
    domain: str | None
    previous_material_type: str | None
    material_type: str | None
    classified_by: str | None


@dataclass(frozen=True)
class ContextBuild:
    """Una construcción del historial (``ContextBuildRecord``)."""

    built_at: str
    previous_built_at: str | None
    built_with_version: str | None
    taxonomy_manifest_used: bool
    ai_classification_model: str | None
    ai_enrichment_model: str | None
    classified: int
    unclassified: int
    changes: list[ContextChangeRow]


def parse_history(text: str) -> list[ContextBuild]:
    """Construcciones de un ``CONTEXT_HISTORY.jsonl`` ya leído, las más recientes primero.

    Igual que ``load_context_history`` de doc_organize: una línea que no es un ``ContextBuildRecord`` válido se ignora.
    La API lee el fichero con sus propias comprobaciones (dentro de la carpeta, sin seguir enlaces, con tope de tamaño).
    """
    from doc_organize.core.models import ContextBuildRecord
    from pydantic import ValidationError

    builds: list[ContextBuild] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            record = ContextBuildRecord.model_validate_json(line)
        except (ValidationError, ValueError):
            continue
        builds.append(
            ContextBuild(
                built_at=record.built_at,
                previous_built_at=record.previous_built_at,
                built_with_version=record.built_with_version,
                taxonomy_manifest_used=record.taxonomy_manifest_used,
                ai_classification_model=record.ai_classification_model,
                ai_enrichment_model=record.ai_enrichment_model,
                classified=record.classified,
                unclassified=record.unclassified,
                changes=[
                    ContextChangeRow(
                        source_path=change.source_path,
                        change=str(getattr(change.change, "value", change.change)),
                        previous_domain=change.previous_domain,
                        domain=change.domain,
                        previous_material_type=change.previous_material_type,
                        material_type=change.material_type,
                        classified_by=change.classified_by,
                    )
                    for change in record.changes
                ],
            )
        )
    return sorted(builds, key=lambda build: build.built_at, reverse=True)


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

    Desde 0.14.0 doc_organize valida el nombre al leerlo (G32): un ``context.json`` cambiado desde el recurso (``..``,
    ruta absoluta, nombre reservado) o dañado da ``ContextError`` y cuenta como sin contexto. Reconstruir lo sustituye
    con la carpeta que valida la API.
    """
    from doc_organize import ContextRegistry
    from doc_organize.core.exceptions import ContextError

    try:
        context = asyncio.run(ContextRegistry().load_context(_project(name, output_root, created_at)))
    except (ContextError, OSError, ValueError):
        return None
    return str(context.output_folder_name)


def _organized(document: Any, output_folder_name: str) -> str:
    """Copia del original en la carpeta reorganizada, relativa a la carpeta del proyecto: junto al ``.md`` copiado
    (``DomainDocument.organized_path``, que ya desambigua los nombres repetidos, L-8d)."""
    folder = PurePosixPath(str(document.organized_path)).parent
    return PurePosixPath(output_folder_name, folder, Path(document.source_path).name).as_posix()


def _traceability(document: Any) -> dict[str, Any]:
    """Campos 1.5.0 de ``DomainDocument`` para ``ContextDoc`` (``ai_filled`` son ``StrEnum`` o texto)."""
    return {
        "author": document.author,
        "description": document.description,
        "keywords": list(document.keywords),
        "language": document.language,
        "ai_filled": [str(getattr(item, "value", item)) for item in document.ai_filled],
        "rules_domain": document.rules_domain,
        "rules_confidence": document.rules_confidence,
        "ai_domain": document.ai_domain,
        "ai_confidence": document.ai_confidence,
        "ai_reasoning": document.ai_reasoning,
        "material_type_confidence": document.material_type_confidence,
    }


def _unclassified(context: Any) -> list[ContextDoc]:
    """Documentos sin clasificar (G42, doc_organize 1.6.0): con su motivo, lo que propusieron las reglas y sus
    propiedades si ``unclassified_details`` los trae (uno por ruta, en el mismo orden); si no (contexto de 1.5.0 o
    detalle dañado), solo el nombre y la extensión, como hasta 1.5.0."""
    details = list(getattr(context, "unclassified_details", None) or [])
    paths = list(context.unclassified_documents)
    if [detail.source_path for detail in details] == paths:
        return [
            ContextDoc(
                domain_slug=None,
                title=detail.title or Path(detail.source_path).name,
                document_type=detail.document_type,
                material_type=None,
                material_type_name=None,
                source_path=detail.source_path,
                organized_path=None,
                author=detail.author,
                description=detail.description,
                keywords=list(detail.keywords),
                language=detail.language,
                rules_domain=detail.rules_domain,
                rules_confidence=detail.rules_confidence,
                unclassified_reason=str(detail.reason),
            )
            for detail in details
        ]
    return [
        ContextDoc(
            domain_slug=None,
            title=Path(path).name,
            document_type=Path(path).suffix.lstrip(".").lower() or None,
            material_type=None,
            material_type_name=None,
            source_path=path,
            organized_path=None,
        )
        for path in paths
    ]


def _outcome(context: Any, failed: list[tuple[str, str]], missing: int) -> ContextOutcome:
    failed_paths = {path for path, _ in failed}
    docs: list[ContextDoc] = []
    domains: list[dict[str, Any]] = []
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
            organized = _organized(document, context.output_folder_name)
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
                    **_traceability(document),
                )
            )
    docs.extend(_unclassified(context))
    return ContextOutcome(
        output_folder_name=context.output_folder_name,
        domains=domains,
        documents=docs,
        failed=failed,
        missing=missing,
        site_built=bool(context.site_built),
        built_with_version=context.built_with_version,
        ai_classification_model=context.model_for_task("classify") if context.ai_stats.scope != "off" else None,
        ai_enrichment_model=context.model_for_task("enrich") if context.ai_stats.enrich else None,
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

    from app.integrations.doc_organize.ai import build_limits, classification_stats, enrichment_stats, llm_client

    uses_ai = request.ai_scope != "off" or request.enrich
    if uses_ai and request.ai is None:
        raise ValueError("La clasificación o las descripciones con IA necesitan la conexión de la familia litellm")
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

    def _ai_progress(event: Any) -> None:  # un documento enviado a la IA: clasificar (Sub-fase B) o describir (1.5.0)
        stage = "context_enrichment" if event.phase == "enrichment" else "context_ai"
        on_progress(stage, int(event.processed), int(event.total) if event.total else None, None)

    async def _classify() -> Any:
        kwargs: dict[str, Any] = {
            "candidate_domains": request.candidate_domains or None,
            "threshold": request.threshold,
            "output_folder_name": request.output_folder_name,
            "taxonomy_manifest": manifest,
            "taxonomy_template_name": request.template_name if manifest is not None else None,
            "cancel_token": token,
        }
        if not uses_ai or request.ai is None:
            return await ContextBuilder().build(project, documents, **kwargs)
        tasks: list[Any] = (["classify"] if request.ai_scope != "off" else []) + (["enrich"] if request.enrich else [])
        # Los límites son argumentos comunes de build(); cada fase cuenta su propio presupuesto (doc_organize 1.5.0).
        kwargs |= {
            "on_progress": _ai_progress,
            "ai_scope": request.ai_scope,
            "enrich": request.enrich,
            **build_limits(request.ai, tasks),
        }
        async with llm_client(request.ai) as llm:
            return await ContextBuilder().build(project, documents, llm=llm, **kwargs)

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
            search_excluded: list[str] = []
            generator = SiteGenerator()
            if request.build_site:
                on_progress("context_site", 0, None, None)
                site = await generator.generate(project, context, build=False)
                search_excluded = list(site.search_excluded)
                context.site_generated = True
                try:
                    await generator.build_site(project, timeout=request.site_timeout)
                except SiteBuildError as exc:
                    context.site_built = False
                    # La causa es la última línea de la salida de Zensical: recortar str(exc) por el principio la perdía.
                    site_error = (exc.cause or str(exc))[:MAX_ERROR_CHARS]
                else:
                    context.site_built = True
            else:
                await generator.delete_site(project)
                context.site_generated = False
                context.site_built = False
            await ContextRegistry().save_context(project, context)
        outcome = _outcome(context, failed, missing)
        outcome.site_error = site_error
        outcome.site_search_excluded = search_excluded
        outcome.ai = classification_stats(context) if request.ai_scope != "off" else None
        outcome.enrichment = enrichment_stats(context) if request.enrich else None
        return outcome

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

    ``expected_folder`` es la carpeta de la vista previa confirmada: si ``context.json`` dice otra, no se borra nada.
    Sin ``context.json`` se borra la carpeta de la vista previa. Uno no válido (G32: lo rechaza doc_organize al leerlo)
    no se borra: hay que reconstruir antes.

    Raises:
        ContextFolderInvalidError: La carpeta de ``context.json`` no es la de la vista previa.
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
        if folder != expected_folder:
            raise ContextFolderInvalidError()
        await Reorganizer().delete_output(project, context)
        await SiteGenerator().delete_site(project)
        await registry.delete_context(project)
        return True

    try:
        return asyncio.run(_run())
    except (DocOrganizeError, OSError) as exc:
        raise DocOrganizeOperationError("doc_organize no pudo borrar el contexto.") from exc
