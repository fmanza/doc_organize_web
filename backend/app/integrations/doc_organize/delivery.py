"""Entrega del contexto (W8, doc_organize 2.0.0rc1 F3/F7): sitio sin conexión en ZIP y paquete para IA.

Solo se llama desde el subproceso de un job (importa doc_organize **dentro** de las funciones). Firmas verificadas en
2.0.0rc1::

    await SiteGenerator().generate(project, context, *, build, site_dir, timeout, redact_credentials, offline,
                                   llms_txt) -> SiteResult
    check_site_offline(site_dir) -> OfflineSiteReport
    write_site_zip(destination, site_dir, *, project_name, on_progress, cancel_token) -> SiteZipResult
    write_ai_context_bundle(destination, project, context, *, include_text, current_only, redact, max_file_chars,
                            max_full_chars, roots, on_progress, cancel_token) -> AiBundleStats

**El sitio sin conexión no escribe en el destino.** ``generate(offline=True)`` neutraliza las páginas de la carpeta
reorganizada, añade ``_offline/`` y reescribe ``zensical.toml`` en la raíz del proyecto; para no tocar el sitio que
sirve la web (ni exigir destino ``rw`` ni el bloqueo de escritura), se construye sobre una **copia** de la carpeta
reorganizada en el workspace del run. Las rutas de los ``.md`` de conversión del contexto se trasladan a esa raíz
(misma ruta relativa: ``resolve_organized_paths`` da las mismas carpetas, también con colisiones) y la copia se borra
al terminar.
"""

from __future__ import annotations

import asyncio
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.integrations.doc_organize.export import (
    ContextMissingError,
    ExportCancelled,
    ExportRequest,
    ProgressFn,
    _run,
    load_context,
)
from app.integrations.doc_organize.projects import DocOrganizeOperationError


class SiteNotReadyError(Exception):
    """El contexto no tiene carpeta reorganizada (se construyó sin reorganizar o se borró)."""


class OfflineSiteProblemsError(Exception):
    """El sitio no pasa ``check_site_offline``: ``problems`` dice por qué (sin rutas del contenedor)."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


@dataclass(frozen=True)
class OfflineSiteRequest:
    """Qué sitio se construye.

    Attributes:
        export: Proyecto (carpeta de salidas, nombre, fecha) y limpieza de rutas.
        build_root: Carpeta temporal del workspace donde se copia la carpeta reorganizada y se construye.
        llms_txt: Añadir ``llms.txt`` en la raíz del sitio.
        redact: Redactar credenciales en las páginas (ajuste del proyecto).
        timeout: Segundos máximos de ``zensical build``.
    """

    export: ExportRequest
    build_root: Path
    llms_txt: bool
    redact: bool
    timeout: float | None


def reorganized_size(request: ExportRequest) -> int:
    """Bytes de la carpeta reorganizada del contexto (para comprobar la cuota antes de copiarla).

    Raises:
        ContextMissingError, SiteNotReadyError.
    """
    from doc_organize import ProjectLayout

    context = load_context(request)
    if not context.reorganized or not context.output_folder_name:
        raise SiteNotReadyError()
    folder = Path(ProjectLayout(request.output_root).reorganized_dir(context.output_folder_name))
    if not folder.is_dir():
        raise SiteNotReadyError()
    return sum(path.stat().st_size for path in folder.rglob("*") if path.is_file() and not path.is_symlink())


def _moved(context: Any, old_root: Path, new_root: Path) -> Any:
    """``context`` con cada ``markdown_path`` trasladado de ``old_root`` a ``new_root`` (misma ruta relativa)."""

    def move(path: str) -> str:
        try:
            return str(new_root / Path(path).relative_to(old_root))
        except ValueError:
            return path

    domains = [
        domain.model_copy(
            update={
                "documents": [
                    document.model_copy(update={"markdown_path": move(document.markdown_path)})
                    for document in domain.documents
                ]
            }
        )
        for domain in context.domains
    ]
    return context.model_copy(update={"domains": domains})


def _clean(problem: str, request: OfflineSiteRequest) -> str:
    text = problem.replace(str(request.build_root), "").replace(request.build_root.as_posix(), "")
    return request.export.clean(text)


def write_offline_site(
    destination: Path,
    request: OfflineSiteRequest,
    *,
    on_phase: Callable[[str], None],
    on_progress: ProgressFn,
    is_cancelled: Callable[[], bool],
) -> dict[str, Any]:
    """Construye el sitio sin conexión sobre una copia, lo comprueba y lo empaqueta en ``destination`` (reproducible).

    Returns:
        ``sha256``, ``zip_size_bytes``, ``file_count``, ``total_size_bytes``, ``neutralized`` (por tipo),
        ``neutralized_pages``, ``credentials_redacted``, ``search_excluded`` y ``llms_txt``.

    Raises:
        ContextMissingError, SiteNotReadyError, OfflineSiteProblemsError, ExportCancelled, DocOrganizeOperationError.
    """
    from doc_organize import (
        OfflineSiteError,
        Project,
        ProjectLayout,
        SiteGenerator,
        check_site_offline,
        write_site_zip,
    )
    from doc_organize.core.exceptions import DocOrganizeError

    export = request.export
    context = load_context(export)
    if not context.reorganized or not context.output_folder_name:
        raise SiteNotReadyError()
    source = Path(ProjectLayout(export.output_root).reorganized_dir(context.output_folder_name))
    if not source.is_dir():
        raise SiteNotReadyError()
    root = request.build_root
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True)
    try:
        on_phase("site_copy")
        shutil.copytree(source, root / context.output_folder_name, symlinks=True)
        moved = _moved(context, export.output_root, root)
        created_at = (export.created_at or datetime.now()).isoformat()
        project = Project(name=export.project_name, root_path=str(root), created_at=created_at)
        if is_cancelled():
            raise ExportCancelled()
        on_phase("site_build")
        try:
            site = asyncio.run(
                SiteGenerator().generate(
                    project,
                    moved,
                    offline=True,
                    llms_txt=request.llms_txt,
                    redact_credentials=request.redact,
                    timeout=request.timeout,
                )
            )
        except DocOrganizeError as exc:
            raise DocOrganizeOperationError("doc_organize no pudo construir el sitio sin conexión.") from exc
        on_phase("site_check")
        report = check_site_offline(site.site_dir)
        if not report.ok:
            raise OfflineSiteProblemsError([_clean(p, request) for p in report.problems()])
        on_phase("export")
        try:
            zipped = _run(
                lambda token, progress: write_site_zip(
                    destination,
                    site.site_dir,
                    project_name=export.project_name,
                    on_progress=progress,
                    cancel_token=token,
                ),
                on_progress=on_progress,
                is_cancelled=is_cancelled,
            )
        except DocOrganizeOperationError as exc:
            if isinstance(exc.__cause__, OfflineSiteError):
                raise OfflineSiteProblemsError([_clean(p, request) for p in exc.__cause__.problems]) from None
            raise
        return {
            "sha256": zipped.sha256,
            "zip_size_bytes": zipped.zip_size_bytes,
            "file_count": zipped.file_count,
            "total_size_bytes": zipped.total_size_bytes,
            "neutralized": dict(site.neutralized_counts),
            "neutralized_items": sum(site.neutralized_counts.values()),
            "neutralized_pages": len(site.neutralized),
            "credentials_redacted": len(site.credentials_redacted),
            "search_excluded": len(site.search_excluded),
            "llms_txt": request.llms_txt,
        }
    finally:
        shutil.rmtree(root, ignore_errors=True)


@dataclass(frozen=True)
class AiBundleRequest:
    """Opciones del paquete para IA (``write_ai_context_bundle``)."""

    export: ExportRequest
    roots: list[str]
    include_text: bool = True
    current_only: bool = True
    redact: bool = True
    max_file_chars: int | None = None
    max_full_chars: int | None = None


def write_ai_bundle(
    destination: Path, request: AiBundleRequest, *, on_progress: ProgressFn, is_cancelled: Callable[[], bool]
) -> dict[str, Any]:
    """Escribe el paquete para IA en ``destination`` (reproducible, en *streaming*); devuelve sus estadísticas.

    Raises:
        ContextMissingError, ExportCancelled, DocOrganizeOperationError.
    """
    from doc_organize import Project, write_ai_context_bundle

    export = request.export
    context = load_context(export)
    created_at = (export.created_at or datetime.now()).isoformat()
    project = Project(name=export.project_name, root_path=str(export.output_root), created_at=created_at)
    stats = _run(
        lambda token, progress: write_ai_context_bundle(
            destination,
            project,
            context,
            include_text=request.include_text,
            current_only=request.current_only,
            redact=request.redact,
            max_file_chars=request.max_file_chars,
            max_full_chars=request.max_full_chars,
            roots=request.roots,
            on_progress=progress,
            cancel_token=token,
        ),
        on_progress=on_progress,
        is_cancelled=is_cancelled,
    )
    data: dict[str, Any] = stats.model_dump(mode="json")
    return data


__all__ = [
    "AiBundleRequest",
    "ContextMissingError",
    "OfflineSiteProblemsError",
    "OfflineSiteRequest",
    "SiteNotReadyError",
    "reorganized_size",
    "write_ai_bundle",
    "write_offline_site",
]
