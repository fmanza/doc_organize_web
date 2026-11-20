"""``export_zip`` y ``export_xlsx``: exportaciones del proyecto como artefactos del run (WB-5.3, L-7).

- ZIP: ``Conversión/`` del proyecto y ``cache_export.json`` (las entradas de las cachés de todas las carpetas de
  origen). Antes de escribir se calcula su tamaño (``preview_project_zip``): con ``dry_run`` el run devuelve solo eso,
  y sin él se comprueba que caben en la cuota del usuario y en el espacio libre del workspace.
- Excel: la caché (``cache``), los errores de escaneo (``errors``: estado actual e histórico), el historial del
  contexto (``context_history``, 1.5.0) o los documentos del contexto con sus ejes (``context_documents``, 2.0).

``cache_export.json`` y los Excel no llevan rutas del contenedor: las rutas de documentos van relativas a su carpeta de
origen (``2024/facturas/a.pdf``) y los mensajes de error, enmascarados. Excepción aceptada por el mantenedor hasta que
doc_organize lo corrija: los JSON de ``Conversión/`` que van en el ZIP llevan ``source_path`` absoluta (G23).
"""

from __future__ import annotations

import re
import shutil
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any, Final

from app.db.models import Project
from app.domain.documents.paths import DocumentNamer, folder_roots
from app.domain.runs.operations import ExportXlsxParams, ExportZipParams
from app.domain.runs.service import MB, quota_used_bytes
from app.domain.scan.state import folder_state
from app.integrations import doc_organize as library
from app.integrations.doc_organize import ExportCancelled, ExportRequest
from app.integrations.doc_organize.export import ProgressFn
from app.jobs.context import JobCancelled, JobContext, JobFailed
from app.jobs.operations._files import project_paths
from app.jobs.operations.common import require_project
from app.jobs.operations.context import context_folders

EXPORT_DIR: Final = "export"
#: Margen de espacio libre que se deja en el workspace al escribir un ZIP.
FREE_SPACE_MARGIN: Final = 256 * MB
_UNSAFE: Final = re.compile(r"[^\w.-]+", re.UNICODE)


def _file_name(project: Project, suffix: str) -> str:
    """Nombre del fichero exportado a partir del nombre del proyecto (sin caracteres problemáticos)."""
    stem = _UNSAFE.sub("_", project.name).strip("._")[:80] or "proyecto"
    return f"{stem}{suffix}"


def _request(ctx: JobContext, project: Project) -> ExportRequest:
    paths = project_paths(project, ctx)
    source = project.source_location
    folders = sorted(project.source_subpaths, key=str.casefold)
    timeout = ctx.settings.location_probe_timeout_seconds
    namer = DocumentNamer(
        [(subpath, folder_roots(source.container_path, subpath, timeout=timeout)) for subpath in folders], source.name
    )
    return ExportRequest(
        output_root=paths.output.absolute,
        states=[folder_state(paths.state, subpath) for subpath in folders],
        rename=namer.display,
        clean=namer.text,
        project_name=project.name,
        created_at=project.created_at,
    )


def _check_room(ctx: JobContext, size: int) -> None:
    """El ZIP (como mucho ``size`` bytes: sin comprimir) cabe en la cuota del usuario y en el workspace.

    Raises:
        JobFailed: ``quota_exceeded`` o ``export_too_large``.
    """
    quota = ctx.settings.user_quota_mb * MB
    if quota and ctx.created_by is not None:
        with ctx.session_factory() as db:
            free_quota = quota - quota_used_bytes(db, ctx.created_by)
        if size > free_quota:
            raise JobFailed(
                "quota_exceeded",
                f"La exportación ocupa hasta {size // MB} MB y te quedan {max(free_quota, 0) // MB} MB de cuota.",
            )
    free = shutil.disk_usage(ctx.workdir).free
    if size + FREE_SPACE_MARGIN > free:
        raise JobFailed(
            "export_too_large", f"La exportación ocupa hasta {size // MB} MB y el servidor no tiene espacio para ella."
        )


def _progress(ctx: JobContext) -> ProgressFn:
    def on_progress(processed: int, total: int | None, current: str | None) -> None:
        ctx.progress("export", processed, total, current)

    return on_progress


def run_zip(ctx: JobContext, params: ExportZipParams, project: Project | None) -> dict[str, Any]:
    """Calcula el tamaño del ZIP y, sin ``dry_run``, lo escribe como artefacto del run."""
    project = require_project(project)
    request = _request(ctx, project)
    ctx.progress("preview", 0, None)
    size = library.zip_preview(request)
    result: dict[str, Any] = {"file_count": size.files, "total_size_bytes": size.bytes}
    if params.dry_run:
        return result
    if ctx.cancelled:
        raise JobCancelled(result)
    ctx.workdir.mkdir(parents=True, exist_ok=True)
    _check_room(ctx, size.bytes)
    name = _file_name(project, ".zip")
    target = ctx.workdir / EXPORT_DIR / name
    target.parent.mkdir(exist_ok=True)
    try:
        written = library.write_zip(target, request, on_progress=_progress(ctx), is_cancelled=lambda: ctx.cancelled)
    except ExportCancelled:
        raise JobCancelled(result) from None
    except (library.DocOrganizeOperationError, OSError):
        target.unlink(missing_ok=True)
        raise JobFailed("export_failed", "No se pudo escribir la exportación.") from None
    ctx.add_artifact(f"{EXPORT_DIR}/{name}", name=name)
    return {"file_count": written.files, "total_size_bytes": written.bytes, "size_bytes": target.stat().st_size}


#: Sufijo del fichero y función que lo escribe, por ``ExportXlsxParams.kind``.
XLSX_KINDS: Final[dict[str, tuple[str, Callable[..., int]]]] = {
    "cache": ("-cache.xlsx", library.write_cache_xlsx),
    "errors": ("-errores.xlsx", library.write_errors_xlsx),
    "context_history": ("-historial-contexto.xlsx", library.write_context_history_xlsx),
    "context_documents": ("-contexto.xlsx", library.write_context_documents_xlsx),
}


def run_xlsx(ctx: JobContext, params: ExportXlsxParams, project: Project | None) -> dict[str, Any]:
    """Escribe el Excel pedido (``XLSX_KINDS``) como artefacto del run."""
    project = require_project(project)
    request = _request(ctx, project)
    if params.kind == "context_documents":
        _, folders, _ = context_folders(ctx, project)
        request = replace(request, roots=tuple(library.context.scan_roots(folders)))
    suffix, write = XLSX_KINDS[params.kind]
    name = _file_name(project, suffix)
    target: Path = ctx.workdir / EXPORT_DIR / name
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        rows = write(target, request, on_progress=_progress(ctx), is_cancelled=lambda: ctx.cancelled)
    except ExportCancelled:
        raise JobCancelled() from None
    except library.ContextMissingError:
        raise JobFailed("context_not_found", "El proyecto no tiene contexto: constrúyelo primero.") from None
    except (library.DocOrganizeOperationError, OSError):
        target.unlink(missing_ok=True)
        raise JobFailed("export_failed", "No se pudo escribir la exportación.") from None
    ctx.add_artifact(f"{EXPORT_DIR}/{name}", name=name)
    return {"rows": rows, "size_bytes": target.stat().st_size}
