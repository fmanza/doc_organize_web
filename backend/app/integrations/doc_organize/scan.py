"""Escaneo y conversión con ``ScanCommand.run_streaming`` de doc_organize 0.10.0 (WB-4.1; G2, G7, G13).

Solo se llama desde el subproceso de un job: importa doc_organize **dentro** de la función (G15). Recibe y devuelve
tipos propios con rutas absolutas del contenedor; el job las convierte en relativas a la ubicación antes de que
lleguen a la BD o al usuario.

Firma verificada en el tag ``v0.10.0``::

    ScanCommand().run_streaming(paths, output_dir, cache_db, folders_json, error_log_path=, history_log_path=, *,
                                options: ScanOptions, on_progress: ProgressCallback, cancel_token: CancelToken)
        -> AsyncIterator[ScanEvent]

Los errores (``ScanErrorReport``) y la duración (``ScanRunReport``) se leen de los JSONL que escribe la librería en el
estado del proyecto: solo las líneas que añade esta llamada (posición del fichero al empezar).
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from app.integrations.doc_organize.models import configure as configure_models
from app.integrations.doc_organize.projects import DocOrganizeOperationError

CANCEL_POLL_SECONDS: Final = 1.0


@dataclass(frozen=True)
class ScanRequest:
    """Una llamada a ``run_streaming``.

    Attributes:
        folders: Carpetas de origen absolutas (ya resueltas y autorizadas), que también son las raíces de las salidas.
        output_root: Carpeta de salidas del proyecto; las conversiones van a ``conversion_dir/output_subdir``.
        output_subdir: Subcarpeta de las conversiones (la carpeta de origen relativa): doc_organize deriva la salida de
            la carpeta escaneada sin su nombre, así que cada carpeta necesita la suya (G18).
        state_root: Estado del proyecto (caché, historiales) en el volumen local (G5).
        models_dir: Carpeta de modelos (ADR-011).
    """

    folders: list[Path]
    output_root: Path
    state_root: Path
    models_dir: Path
    output_subdir: str = ""
    use_ocr: bool = True
    use_gpu: bool = False
    force: bool = False
    include_audio_video: bool = False
    extract_images: bool = False
    use_picture_description: bool = False


@dataclass(frozen=True)
class ScanProgress:
    """Progreso con unidades (``ProgressEvent`` de doc_organize); ``current`` es una ruta absoluta del contenedor."""

    phase: str
    processed: int
    total: int | None
    current: str | None


@dataclass(frozen=True)
class ScanFailure:
    """Documento que no se pudo convertir (``ScanErrorEntry``), con su ruta absoluta y el mensaje sin sanear."""

    path: str
    message: str
    retry_count: int
    capped: bool


@dataclass
class ScanOutcome:
    """Resultado de una llamada.

    Attributes:
        cancelled: Paró por el ``CancelToken``; lo convertido quedó guardado en la caché.
        summary: Recuentos del ``ScanSummary`` (evento final ``completed`` o ``cancelled``).
        warnings: Avisos del descubrimiento (carpetas que ya no existen…); pueden llevar rutas absolutas.
        failures: Errores de conversión de esta llamada.
        reports: ``ScanRunReport`` de esta llamada (duraciones).
        event_schema_version: ``schema_version`` de los eventos de doc_organize (G7).
    """

    cancelled: bool = False
    summary: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    failures: list[ScanFailure] = field(default_factory=list)
    reports: list[dict[str, Any]] = field(default_factory=list)
    event_schema_version: int | None = None


def _size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _new_lines(path: Path, offset: int) -> list[str]:
    """Líneas añadidas a ``path`` desde ``offset`` (el fichero es *append-only*)."""
    try:
        with path.open("rb") as handle:
            handle.seek(offset)
            data = handle.read()
    except OSError:
        return []
    return [line for line in data.decode("utf-8", errors="replace").splitlines() if line.strip()]


def run_scan(
    request: ScanRequest,
    *,
    on_progress: Callable[[ScanProgress], None],
    is_cancelled: Callable[[], bool],
) -> ScanOutcome:
    """Escanea ``request.folders`` y convierte lo nuevo o modificado; bloquea hasta terminar o cancelar.

    Raises:
        DocOrganizeOperationError: doc_organize abortó el escaneo (mensaje genérico: el de la librería lleva rutas).
    """
    configure_models(request.models_dir)
    from doc_organize import (
        CancelToken,
        DocOrganizeError,
        ProgressEvent,
        ProjectLayout,
        ScanCommand,
        ScanErrorReport,
        ScanEventType,
        ScanOptions,
        ScanRunReport,
    )

    layout = ProjectLayout(request.output_root, state_root=request.state_root)
    options = ScanOptions(
        use_ocr=request.use_ocr,
        use_gpu=request.use_gpu,
        force=request.force,
        include_audio_video=request.include_audio_video,
        extract_images=request.extract_images,
        use_picture_description=request.use_picture_description,
    )
    errors_log, history_log = layout.scan_errors_log, layout.scan_history_log
    errors_offset, history_offset = _size(errors_log), _size(history_log)
    token = CancelToken()
    stop = threading.Event()

    def _bridge() -> None:  # une la cancelación del job (BD) con el CancelToken de la librería (G2)
        while not stop.wait(CANCEL_POLL_SECONDS):
            if is_cancelled():
                token.cancel()
                return

    def _progress(event: ProgressEvent) -> None:
        on_progress(ScanProgress(event.phase, event.processed, event.total, event.current))
        if is_cancelled():  # cada documento: la parada llega antes del siguiente sin esperar al sondeo
            token.cancel()

    outcome = ScanOutcome()

    async def _consume() -> None:
        async for event in ScanCommand().run_streaming(
            [str(folder) for folder in request.folders],
            _conversion_dir(layout.conversion_dir, request.output_subdir),
            layout.cache_db,
            layout.folders_json,
            error_log_path=errors_log,
            history_log_path=history_log,
            options=options,
            on_progress=_progress,
            cancel_token=token,
        ):
            outcome.event_schema_version = event.schema_version
            if event.event == ScanEventType.SCANNED:
                outcome.warnings.extend(str(w) for w in event.data.get("warnings") or [])
            elif event.event in (ScanEventType.COMPLETED, ScanEventType.CANCELLED):
                outcome.summary = dict(event.data)
                outcome.cancelled = event.event == ScanEventType.CANCELLED

    watcher = threading.Thread(target=_bridge, name="dow-scan-cancel", daemon=True)
    watcher.start()
    try:
        asyncio.run(_consume())
    except DocOrganizeError as exc:
        raise DocOrganizeOperationError("doc_organize no pudo completar el escaneo.") from exc
    finally:
        stop.set()
        watcher.join()

    for line in _new_lines(errors_log, errors_offset):
        try:
            report = ScanErrorReport.model_validate_json(line)
        except ValueError:  # una línea dañada no invalida un escaneo ya guardado en la caché
            outcome.warnings.append("Una línea del historial de errores no se pudo leer.")
            continue
        outcome.failures.extend(
            ScanFailure(e.file_path, e.error_message, e.error_retry_count, e.capped) for e in report.entries
        )
    for line in _new_lines(history_log, history_offset):
        try:
            outcome.reports.append(ScanRunReport.model_validate_json(line).model_dump())
        except ValueError:
            continue
    return outcome


def cached_paths(output_root: Path, state_root: Path) -> list[str]:
    """Rutas absolutas de los documentos de la caché del proyecto (vista previa de «forzar reconversión»).

    ``CacheManager(db_path).load_cache() -> dict[str, CacheEntry]`` (verificado en ``v0.10.0``). Sin caché, lista vacía.
    """
    from doc_organize import CacheManager, ProjectLayout

    cache_db = ProjectLayout(output_root, state_root=state_root).cache_db
    if not cache_db.is_file():
        return []

    async def _load() -> list[str]:
        async with CacheManager(cache_db) as cache:
            return sorted(await cache.load_cache())

    return asyncio.run(_load())


def _conversion_dir(base: Path, subdir: str) -> Path:
    return base / subdir if subdir else base


def conversion_dir(output_root: Path, state_root: Path, subdir: str = "") -> Path:
    """Carpeta de las conversiones de una carpeta de origen (``ProjectLayout.conversion_dir`` / ``subdir``)."""
    from doc_organize import ProjectLayout

    return _conversion_dir(Path(ProjectLayout(output_root, state_root=state_root).conversion_dir), subdir)
