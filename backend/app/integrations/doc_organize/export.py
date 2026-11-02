"""Exportaciones del proyecto con ``doc_organize.export`` 0.11.0 (WB-5.3, L-7; cierra G8).

Solo se llama desde el subproceso de un job (importa doc_organize **dentro** de la función). Firmas verificadas en el
tag ``v0.11.0``::

    await load_cache_entries(cache_dbs: Iterable[str | Path]) -> list[CacheEntry]
    load_scan_error_history(history_logs: Iterable[str | Path]) -> list[ScanErrorReport]
    preview_project_zip(entries, *, conversion_dir: Path | None, dedup_report: Path | None) -> ExportStats
    write_project_zip(destination, entries, *, conversion_dir, dedup_report, on_progress, cancel_token) -> ExportStats
    write_cache_xlsx(destination, entries, *, on_progress, cancel_token) -> int
    write_scan_errors_xlsx(destination, entries, history, *, on_progress, cancel_token) -> int

Las escrituras son síncronas y borran el fichero parcial si se cancelan (``OperationCancelledError``). La caché guarda
rutas **absolutas** del contenedor: antes de escribir nada, cada ``file_path`` pasa por ``ExportRequest.rename`` y cada
mensaje de error por ``ExportRequest.clean``: ni ``cache_export.json`` ni los Excel llevan rutas del servidor. Los JSON
de ``Conversión/`` que van en el ZIP son los que escribió doc_organize, con ``source_path`` absoluta (G23, aceptado por
el mantenedor hasta que doc_organize lo corrija).
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from app.integrations.doc_organize.projects import DocOrganizeOperationError

if TYPE_CHECKING:
    from doc_organize import CacheEntry, CancelToken, ScanErrorReport

CANCEL_POLL_SECONDS: Final = 1.0
ProgressFn = Callable[[int, int | None, str | None], None]


class ExportCancelled(Exception):  # noqa: N818 - nombre del dominio (como JobCancelled)
    """La exportación paró por cancelación; doc_organize ya borró el fichero parcial."""


@dataclass(frozen=True)
class ExportRequest:
    """Qué se exporta.

    Attributes:
        output_root: Carpeta de salidas del proyecto (``Conversión/`` cuelga de ella).
        states: Carpeta de estado de cada carpeta de origen (una caché y un historial de errores en cada una).
        rename: Ruta absoluta de un documento → ruta que ve el usuario (``2024/facturas/a.pdf``).
        clean: Mensaje de error → mensaje sin rutas del contenedor.
    """

    output_root: Path
    states: list[Path]
    rename: Callable[[str], str]
    clean: Callable[[str], str]
    #: Entradas ya cargadas (la vista previa y la escritura del ZIP leen las cachés una sola vez).
    loaded: dict[str, Any] = field(default_factory=dict, compare=False, repr=False)


@dataclass(frozen=True)
class ExportSize:
    """Ficheros y bytes sin comprimir de un ZIP (``ExportStats``)."""

    files: int
    bytes: int


def _entries(request: ExportRequest) -> list[CacheEntry]:
    from doc_organize import ProjectLayout
    from doc_organize.export import load_cache_entries

    if "entries" in request.loaded:
        cached: list[CacheEntry] = request.loaded["entries"]
        return cached
    caches = [ProjectLayout(request.output_root, state_root=state).cache_db for state in request.states]
    entries = asyncio.run(load_cache_entries(caches))
    request.loaded["entries"] = [
        entry.model_copy(
            update={
                "file_path": request.rename(entry.file_path),
                "error_message": request.clean(entry.error_message) if entry.error_message else None,
            }
        )
        for entry in entries
    ]
    return _entries(request)


def _history(request: ExportRequest) -> list[ScanErrorReport]:
    from doc_organize import ProjectLayout
    from doc_organize.export import load_scan_error_history

    logs = [ProjectLayout(request.output_root, state_root=state).scan_errors_log for state in request.states]
    return [
        report.model_copy(
            update={
                "entries": [
                    entry.model_copy(
                        update={
                            "file_path": request.rename(entry.file_path),
                            "error_message": request.clean(entry.error_message),
                        }
                    )
                    for entry in report.entries
                ]
            }
        )
        for report in load_scan_error_history(logs)
    ]


def _conversion_dir(output_root: Path) -> Path:
    from doc_organize import ProjectLayout

    return Path(ProjectLayout(output_root).conversion_dir)


def zip_preview(request: ExportRequest) -> ExportSize:
    """Ficheros y bytes que tendría el ZIP del proyecto, sin escribirlo (recorre ``Conversión/``)."""
    from doc_organize.export import preview_project_zip

    stats = preview_project_zip(_entries(request), conversion_dir=_conversion_dir(request.output_root))
    return ExportSize(stats.file_count, stats.total_size_bytes)


def _run(
    write: Callable[[CancelToken, Callable[[Any], None]], Any],
    *,
    on_progress: ProgressFn,
    is_cancelled: Callable[[], bool],
) -> Any:
    """Ejecuta ``write`` con un ``CancelToken`` unido a la cancelación del job y traduce las excepciones."""
    from doc_organize import CancelToken, DocOrganizeError, OperationCancelledError, ProgressEvent

    token = CancelToken()
    stop = threading.Event()

    def _bridge() -> None:
        while not stop.wait(CANCEL_POLL_SECONDS):
            if is_cancelled():
                token.cancel()
                return

    def _progress(event: ProgressEvent) -> None:
        on_progress(event.processed, event.total, event.current)
        if is_cancelled():
            token.cancel()

    watcher = threading.Thread(target=_bridge, name="dow-export-cancel", daemon=True)
    watcher.start()
    try:
        return write(token, _progress)
    except OperationCancelledError:
        raise ExportCancelled() from None
    except DocOrganizeError as exc:
        raise DocOrganizeOperationError("doc_organize no pudo completar la exportación.") from exc
    finally:
        stop.set()
        watcher.join()


def write_zip(
    destination: Path, request: ExportRequest, *, on_progress: ProgressFn, is_cancelled: Callable[[], bool]
) -> ExportSize:
    """Escribe el ZIP del proyecto (``Conversión/`` y ``cache_export.json``) en ``destination``.

    Raises:
        ExportCancelled: Se canceló (el parcial ya está borrado).
        DocOrganizeOperationError: doc_organize no pudo escribirlo.
    """
    from doc_organize.export import write_project_zip

    entries = _entries(request)
    conversion = _conversion_dir(request.output_root)
    stats = _run(
        lambda token, progress: write_project_zip(
            destination, entries, conversion_dir=conversion, on_progress=progress, cancel_token=token
        ),
        on_progress=on_progress,
        is_cancelled=is_cancelled,
    )
    return ExportSize(stats.file_count, stats.total_size_bytes)


def write_cache_xlsx(
    destination: Path, request: ExportRequest, *, on_progress: ProgressFn, is_cancelled: Callable[[], bool]
) -> int:
    """Excel con todas las entradas de las cachés del proyecto; devuelve las filas escritas."""
    from doc_organize.export import write_cache_xlsx as _write

    entries = _entries(request)
    rows: int = _run(
        lambda token, progress: _write(destination, entries, on_progress=progress, cancel_token=token),
        on_progress=on_progress,
        is_cancelled=is_cancelled,
    )
    return rows


def write_errors_xlsx(
    destination: Path, request: ExportRequest, *, on_progress: ProgressFn, is_cancelled: Callable[[], bool]
) -> int:
    """Excel de errores de escaneo (estado actual e histórico de todas las carpetas); devuelve las filas escritas."""
    from doc_organize.export import write_scan_errors_xlsx

    entries, history = _entries(request), _history(request)
    rows: int = _run(
        lambda token, progress: write_scan_errors_xlsx(
            destination, entries, history, on_progress=progress, cancel_token=token
        ),
        on_progress=on_progress,
        is_cancelled=is_cancelled,
    )
    return rows
