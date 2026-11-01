"""``scan``: escanea carpetas de origen del proyecto y convierte lo nuevo o modificado a su carpeta de salidas (WB-4.1).

Cada carpeta de origen es un **ámbito propio de doc_organize** (decisión del mantenedor, Fase 4):

- salidas en ``<salidas>/Conversión/<carpeta>/…`` y caché e historiales en ``/data/projects/<id>/folders/<clave>/``.
  doc_organize deriva la ruta de cada salida de la carpeta escaneada **sin su nombre**: con una salida común,
  ``2024/x/a.pdf`` y ``2025/x/a.pdf`` acabarían en el mismo ``x/a.md`` (G18);
- una llamada a doc_organize por carpeta: la caché solo se guarda al final de cada llamada (G16), así que un corte a
  mitad pierde como mucho la carpeta en curso; si una carpeta falla, se sigue con las demás;
- «forzar» (vacía la caché y borra las salidas de lo que ya no está) actúa carpeta a carpeta, sin tocar las de las
  demás ni las de carpetas que ya no son del proyecto. Su vista previa (``dry_run``) cuenta la caché, cuántos
  documentos ya no existen y el tamaño de las salidas, sin hashear el origen.

Las rutas absolutas de doc_organize se convierten en relativas a la ubicación antes de guardarse o mostrarse.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Final

from sqlalchemy import select, update

from app.core.redact import PathRedactor
from app.db.models import Project, Run, ScanError, ScannedFolder, Worker, utcnow
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction
from app.domain.runs.operations import ScanParams
from app.domain.scan.options import missing_options
from app.integrations import doc_organize as library
from app.integrations.doc_organize import ScanFailure, ScanOutcome, ScanProgress, ScanRequest
from app.jobs.context import JobCancelled, JobContext, JobFailed
from app.jobs.operations._files import measure, project_paths, require_rw, resolve_in
from app.jobs.operations.common import WORKER_CONTEXT, require_project

MAX_MESSAGE: Final = 2000
#: Errores que se guardan por run (el total va en ``result.errors``): acota ``config.db`` ante orígenes enormes.
MAX_SAVED_ERRORS: Final = 10_000
MAX_WARNINGS: Final = 20
#: Recuentos del ``ScanSummary`` que se suman entre llamadas.
SUMMARY_COUNTS: Final = (
    "scanned",
    "new",
    "modified",
    "unchanged",
    "converted",
    "conversion_errors",
    "ocr_required",
    "ocr_processed",
    "error_retries",
    "error_retries_capped",
)
SUMMARY_SECONDS: Final = ("duration_seconds", "discovery_duration_seconds", "total_conversion_seconds")
#: Fase de doc_organize → fase que ve el usuario.
PHASES: Final = {"started": "discovery", "discovery": "discovery", "conversion": "conversion", "ocr": "ocr"}
FOLDERS_STATE_DIR: Final = "folders"


@dataclass(frozen=True)
class Folder:
    """Carpeta de origen que se escanea y su ámbito de doc_organize.

    Attributes:
        subpath: Relativa a la ubicación de origen (``""`` = la raíz).
        absolute: Ruta resuelta en el contenedor.
        state: Caché e historiales de esta carpeta.
    """

    subpath: str
    absolute: Path
    state: Path

    @property
    def label(self) -> str:
        return self.subpath or "(raíz)"


def folder_state(project_state: Path, subpath: str) -> Path:
    """Carpeta de estado de una carpeta de origen: clave estable derivada de su ruta relativa (sin caracteres raros)."""
    return project_state / FOLDERS_STATE_DIR / hashlib.sha256(subpath.encode("utf-8")).hexdigest()[:16]


class PathMasker:
    """Convierte rutas absolutas del contenedor en relativas a la ubicación (``«Origen»/sub/doc.pdf``).

    Las raíces deben ser rutas resueltas (las que da el resolvedor), igual que las que devuelve doc_organize.
    """

    def __init__(self, roots: list[tuple[Path, str]]) -> None:
        # Las raíces más largas primero: una ruta se atribuye a la carpeta más concreta.
        self._roots = sorted(((str(path), label) for path, label in roots), key=lambda r: -len(r[0]))
        self._redactor = PathRedactor(self._roots)

    def relative(self, path: str) -> str:
        """``path`` relativa a su ubicación; si no está bajo ninguna raíz, solo el nombre del fichero."""
        for root, _ in self._roots:
            if path == root or path.startswith(root.rstrip("/") + "/"):
                return PurePosixPath(path[len(root) :].lstrip("/")).as_posix() or "."
        return PurePosixPath(path.replace("\\", "/")).name

    def text(self, message: str) -> str:
        """``message`` sin rutas del contenedor: cada raíz por su etiqueta y cualquier otra ruta por ``«ruta»``."""
        return self._redactor.text(message)


def _check_worker_options(ctx: JobContext, params: ScanParams) -> None:
    """Vuelve a comprobar las opciones contra las capacidades del worker que ejecuta el run."""
    with ctx.session_factory() as db:
        worker_id = db.scalar(select(Run.worker_id).where(Run.id == ctx.run_id))
        worker = db.get(Worker, worker_id) if worker_id else None
        capabilities = worker.capabilities if worker is not None else None
    if capabilities is not None and missing_options(params, [capabilities]):
        raise JobFailed("option_unavailable", "Este worker no puede atender alguna de las opciones del escaneo.")


def _folders(ctx: JobContext, project: Project, params: ScanParams, state: Path) -> list[Folder]:
    """Carpetas a escanear, re-resueltas; las que ya no existen se avisan y se saltan (con «forzar», se para)."""
    wanted = params.folders or project.source_subpaths
    if any(f not in project.source_subpaths for f in wanted):
        raise JobFailed("folder_not_saved", "Alguna carpeta ya no es una carpeta de origen del proyecto.")
    result: list[Folder] = []
    for subpath in wanted:
        try:
            absolute = resolve_in(project.source_location, subpath, ctx).absolute
        except JobFailed as exc:
            if exc.code != "folder_missing" or params.force:
                raise
            ctx.log(exc.message, level="warning")
            continue
        result.append(Folder(subpath, absolute, folder_state(state, subpath)))
    if not result:
        raise JobFailed("folder_missing", "Ninguna de las carpetas elegidas existe ya en el origen.")
    return result


def _inside(path: str, root: Path) -> bool:
    return path == str(root) or path.startswith(str(root).rstrip("/") + "/")


def _check_force(folders: list[Folder], output: Path) -> dict[str, list[str]]:
    """Condiciones de «forzar» (borra las salidas de lo que doc_organize no vea): devuelve la caché de cada carpeta.

    Raises:
        JobFailed: La caché de una carpeta tiene documentos de fuera de ella (doc_organize les calcularía una salida
            plana y podría borrar la de otro documento), o una carpeta no se puede leer (doc_organize la trataría como
            vacía y borraría todas sus salidas, G19).
    """
    cached: dict[str, list[str]] = {}
    for folder in folders:
        try:
            with os.scandir(folder.absolute) as entries:
                next(entries, None)
        except OSError:
            raise JobFailed(
                "folder_unreadable", f"No se puede leer la carpeta «{folder.label}»: no se fuerza nada."
            ) from None
        paths = library.cached_paths(output, folder.state)
        outside = sum(1 for path in paths if not _inside(path, folder.absolute))
        if outside:
            raise JobFailed(
                "cache_outside_folders",
                f"La caché de «{folder.label}» tiene {outside} documentos de fuera de la carpeta: «Forzar reconversión» "
                "borraría salidas que no les corresponden. Usa «Vaciar histórico» y vuelve a escanear.",
            )
        cached[folder.subpath] = paths
    return cached


def _preview(ctx: JobContext, folders: list[Folder], output: Path) -> dict[str, Any]:
    """Vista previa de «forzar reconversión»: documentos en caché, cuántos ya no existen y tamaño de las salidas."""
    ctx.progress("preview", 0, None)
    cached = [path for paths in _check_force(folders, output).values() for path in paths]
    missing = 0
    for index, path in enumerate(cached, start=1):
        if index % 200 == 0:
            ctx.check_cancelled()
            ctx.progress("preview", index, len(cached))
        if not os.path.lexists(path):
            missing += 1
    files = size = 0
    for folder in folders:
        tree = measure(library.conversion_dir(output, folder.state, folder.subpath), ctx, "measure_outputs")
        files, size = files + tree.files, size + tree.bytes
    ctx.progress("preview", len(cached), len(cached))
    return {"cached": len(cached), "orphaned": missing, "output_files": files, "output_bytes": size}


def _save_failures(ctx: JobContext, project: Project, failures: list[ScanFailure], masker: PathMasker) -> None:
    """Guarda los errores (ya limitados por quien llama a ``MAX_SAVED_ERRORS`` por run)."""
    if not failures:
        return
    with ctx.session_factory() as db:
        db.add_all(
            ScanError(
                run_id=ctx.run_id,
                project_id=project.id,
                path=masker.relative(f.path)[:4096],
                message=masker.text(f.message)[:MAX_MESSAGE],
                retry_count=f.retry_count,
                capped=f.capped,
            )
            for f in failures
        )
        db.commit()


def _mark_used(ctx: JobContext, project: Project, subpath: str) -> None:
    with ctx.session_factory() as db:
        db.execute(
            update(ScannedFolder)
            .where(ScannedFolder.project_id == project.id, ScannedFolder.subpath == subpath)
            .values(used=True, last_scanned_at=utcnow(), last_run_id=ctx.run_id)
        )
        db.commit()


def _accumulate(total: dict[str, Any], outcome: ScanOutcome) -> None:
    for key in (*SUMMARY_COUNTS, *SUMMARY_SECONDS):
        value = outcome.summary.get(key)
        if isinstance(value, int | float):
            total[key] = round(total.get(key, 0) + value, 3) if key in SUMMARY_SECONDS else total.get(key, 0) + value
    total["errors"] = total.get("errors", 0) + len(outcome.failures)
    total["warnings"] = total.get("warnings", 0) + len(outcome.warnings)
    if outcome.event_schema_version is not None:
        total["event_schema_version"] = outcome.event_schema_version


def run(ctx: JobContext, params: ScanParams, project: Project | None) -> dict[str, Any]:
    """Escanea (o, con ``force`` y ``dry_run``, hace la vista previa) y devuelve los recuentos."""
    project = require_project(project)
    paths = project_paths(project, ctx)
    source = project.source_location
    output = paths.output.absolute
    folders = _folders(ctx, project, params, paths.state)
    if params.dry_run:
        return _preview(ctx, folders, output)
    require_rw(project.destination_location)
    _check_worker_options(ctx, params)
    if params.force:
        _check_force(folders, output)
    masker = PathMasker(
        [
            (resolve_in(source, "", ctx).absolute, f"«{source.name}»"),
            (output, "«salidas»"),
            (paths.state, "«estado»"),
        ]
    )
    if not library.models_status(ctx.settings.models_dir).ready:
        ctx.log("Faltan los modelos de Docling: los PDF y las imágenes no se podrán convertir.", level="warning")

    def on_progress(event: ScanProgress) -> None:
        current = masker.relative(event.current) if event.current else None
        ctx.progress(PHASES.get(event.phase, event.phase), event.processed, event.total, current)

    result: dict[str, Any] = {"folders": len(folders), "force": params.force}
    failed: list[str] = []
    warned = saved = 0
    for index, folder in enumerate(folders, start=1):
        if ctx.cancelled:
            raise JobCancelled(result)
        if len(folders) > 1:
            ctx.log(f"Carpeta {index} de {len(folders)}: «{folder.label}».")
        folder.state.mkdir(parents=True, exist_ok=True)
        request = ScanRequest(
            folders=[folder.absolute],
            output_root=output,
            output_subdir=folder.subpath,
            state_root=folder.state,
            models_dir=ctx.settings.models_dir,
            use_ocr=params.use_ocr,
            use_gpu=params.use_gpu,
            force=params.force,
            include_audio_video=params.include_audio_video,
            extract_images=params.extract_images,
            use_picture_description=params.use_picture_description,
        )
        try:
            outcome = library.run_scan(request, on_progress=on_progress, is_cancelled=lambda: ctx.cancelled)
        except (library.DocOrganizeOperationError, OSError):
            # Un corte de red o un fallo de doc_organize en esta carpeta no impide escanear las demás.
            failed.append(folder.label)
            ctx.log(f"No se pudo escanear la carpeta «{folder.label}».", level="error")
            continue
        _accumulate(result, outcome)
        room = max(0, MAX_SAVED_ERRORS - saved)
        _save_failures(ctx, project, outcome.failures[:room], masker)
        saved += min(room, len(outcome.failures))
        for warning in outcome.warnings[: max(0, MAX_WARNINGS - warned)]:
            ctx.log(masker.text(warning), level="warning")
        warned += len(outcome.warnings)
        if outcome.cancelled:
            raise JobCancelled(result)
        _mark_used(ctx, project, folder.subpath)
    if params.force:
        with ctx.session_factory() as db:
            audit.record(
                db,
                action=AuditAction.PROJECT_SCAN_FORCE,
                ctx=WORKER_CONTEXT,
                actor_id=ctx.created_by,
                target_type="project",
                target_id=project.id,
                details={"run_id": ctx.run_id, "converted": result.get("converted", 0), "failed": len(failed)},
            )
            db.commit()
    if failed:
        result["failed_folders"] = len(failed)
        raise JobFailed(
            "scan_failed", f"No se pudieron escanear {len(failed)} de {len(folders)} carpetas.", result=result
        )
    ctx.progress("done", 1, 1)
    return result
