"""Sondeo de una ubicación: existencia, lectura, latencia de ``stat``, espacio libre y escritura (si es ``rw``).

El resultado no depende de la BD: ``service.probe_location`` lo guarda en la fila. Todo se ejecuta con el timeout de
``location_probe_timeout_seconds``; un montaje colgado da ``unavailable``.
"""

from __future__ import annotations

import os
import shutil
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from app.core.config import Settings
from app.domain.locations.errors import LocationUnavailableError
from app.domain.locations.paths import run_with_timeout

ProbeStatus = Literal["ok", "degraded", "unavailable"]
GB = 1024**3


@dataclass(frozen=True)
class ProbeResult:
    """Resultado de un sondeo.

    Attributes:
        status: ``ok``, ``degraded`` o ``unavailable``.
        reasons: Códigos de los problemas encontrados (``missing``, ``unreadable``, ``timeout``, ``slow``,
            ``low_space``, ``not_writable``).
        latency_ms: Duración del ``stat`` de la raíz.
        free_bytes: Espacio libre del sistema de ficheros.
        writable: Si se pudo escribir y borrar un fichero temporal (``None`` si no se comprobó, en ``ro``).
    """

    status: ProbeStatus
    reasons: list[str] = field(default_factory=list)
    latency_ms: float | None = None
    free_bytes: int | None = None
    writable: bool | None = None


def _measure(root: Path, check_write: bool) -> tuple[list[str], float | None, int | None, bool | None]:
    start = time.perf_counter()
    try:
        root.stat()
    except OSError:
        return ["missing"], None, None, None
    latency_ms = round((time.perf_counter() - start) * 1000, 2)
    if not os.path.isdir(root):
        return ["missing"], latency_ms, None, None
    try:
        with os.scandir(root) as entries:
            next(entries, None)
    except OSError:
        return ["unreadable"], latency_ms, None, None
    try:
        free: int | None = shutil.disk_usage(root).free
    except OSError:
        free = None
    writable: bool | None = None
    if check_write:
        probe_file = root / f".dow-probe-{uuid.uuid4().hex}"
        try:
            probe_file.write_bytes(b"dow")
            probe_file.unlink()
            writable = True
        except OSError:
            writable = False
            try:
                probe_file.unlink(missing_ok=True)
            except OSError:
                pass  # sin permiso de escritura tampoco hay nada que borrar
    return [], latency_ms, free, writable


def probe(root: Path, *, access: str, settings: Settings) -> ProbeResult:
    """Sondea ``root``; con ``access == "rw"`` comprueba también la escritura."""
    try:
        reasons, latency_ms, free_bytes, writable = run_with_timeout(
            lambda: _measure(root, check_write=access == "rw"), settings.location_probe_timeout_seconds
        )
    except LocationUnavailableError:
        return ProbeResult(status="unavailable", reasons=["timeout"])
    if reasons:
        return ProbeResult(status="unavailable", reasons=reasons, latency_ms=latency_ms)
    if latency_ms is not None and latency_ms > settings.location_latency_degraded_ms:
        reasons.append("slow")
    if free_bytes is not None and settings.location_min_free_gb and free_bytes < settings.location_min_free_gb * GB:
        reasons.append("low_space")
    if writable is False:
        reasons.append("not_writable")
    return ProbeResult(
        status="degraded" if reasons else "ok",
        reasons=reasons,
        latency_ms=latency_ms,
        free_bytes=free_bytes,
        writable=writable,
    )
