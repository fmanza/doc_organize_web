"""Capacidades de la instancia: GPU, audio/vídeo (Whisper + ffmpeg) y LibreOffice (rodeo de G12 y G15).

doc_organize 0.9.3 no tiene un punto de entrada público para sus detectores (G12) e importar cualquiera de ellos carga
el paquete entero, con Docling y torch (G15: ~4 300 módulos y decenas de segundos en frío). Por eso la API **nunca**
los importa: lanza este módulo como subproceso (``python -m app.integrations.doc_organize.capabilities``), que imprime
el resultado en JSON, y lo guarda en una caché de proceso. En la Fase 3 lo publicará cada worker.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Literal

logger = logging.getLogger(__name__)

#: Directorio que contiene el paquete ``app`` (``backend/`` en desarrollo, ``/app`` en la imagen).
_APP_PARENT: Final = Path(__file__).resolve().parents[3]
PROBE_TIMEOUT_SECONDS: Final = 180
CACHE_TTL_SECONDS: Final = 3600


@dataclass(frozen=True)
class Capabilities:
    """Lo que la instancia puede hacer al convertir documentos.

    Attributes:
        gpu_support_installed: ``torch`` está instalado (también en la imagen CPU, que lo trae para Docling).
        gpu_active: Hay una GPU CUDA utilizable en este contenedor.
        asr_installed: Whisper (extra ``av``) está instalado.
        ffmpeg_installed: ``ffmpeg`` está en el ``PATH``.
        av_ready: Audio y vídeo convertibles (``asr_installed`` y ``ffmpeg_installed``).
        libreoffice_installed: ``soffice`` está en el ``PATH`` (``.xls`` legado).
    """

    gpu_support_installed: bool
    gpu_active: bool
    asr_installed: bool
    ffmpeg_installed: bool
    av_ready: bool
    libreoffice_installed: bool


@dataclass(frozen=True)
class CapabilitiesSnapshot:
    """Último resultado conocido.

    Attributes:
        status: ``pending`` (aún no hay resultado), ``ok`` o ``error`` (el último sondeo falló).
        checked_at: Cuándo se obtuvo ``capabilities``.
        capabilities: Resultado, o ``None`` si nunca se ha obtenido.
    """

    status: Literal["pending", "ok", "error"]
    checked_at: datetime | None
    capabilities: Capabilities | None


def collect() -> Capabilities:  # pragma: no cover - se ejecuta en el subproceso, con Docling y torch cargados
    """Llama a los detectores de doc_organize (G12: módulos internos, no API pública)."""
    from doc_organize.utils.av_detector import detect_av_status
    from doc_organize.utils.gpu_detector import detect_gpu_status
    from doc_organize.utils.office_detector import detect_office_status

    gpu = detect_gpu_status()
    av = detect_av_status()
    office = detect_office_status()
    return Capabilities(
        gpu_support_installed=gpu.gpu_support_installed,
        gpu_active=gpu.gpu_active,
        asr_installed=av.asr_installed,
        ffmpeg_installed=av.ffmpeg_installed,
        av_ready=av.ready,
        libreoffice_installed=office.libreoffice_installed,
    )


def run_probe(timeout: float = PROBE_TIMEOUT_SECONDS) -> Capabilities:
    """Ejecuta el subproceso y devuelve su resultado.

    Raises:
        RuntimeError: El subproceso falló, se agotó el tiempo o su salida no es válida.
    """
    try:
        completed = subprocess.run(  # noqa: S603 - comando fijo con el intérprete actual
            [sys.executable, "-m", "app.integrations.doc_organize.capabilities"],
            cwd=_APP_PARENT,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("El sondeo de capacidades no terminó a tiempo") from exc
    if completed.returncode != 0:
        raise RuntimeError(f"El sondeo de capacidades terminó con código {completed.returncode}")
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    try:
        return Capabilities(**json.loads(lines[-1]))
    except (IndexError, TypeError, ValueError) as exc:
        raise RuntimeError("Salida del sondeo de capacidades no válida") from exc


class CapabilitiesCache:
    """Caché de proceso: devuelve el último resultado y lo recalcula en segundo plano cuando caduca.

    Nunca bloquea una petición: mientras no hay resultado responde ``pending``.
    """

    def __init__(self, ttl_seconds: float = CACHE_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._snapshot = CapabilitiesSnapshot(status="pending", checked_at=None, capabilities=None)
        self._refreshed_at: float | None = None
        self._running = False

    def get(self) -> CapabilitiesSnapshot:
        """Último resultado; lanza un sondeo en segundo plano si no hay o ha caducado."""
        with self._lock:
            stale = self._refreshed_at is None or time.monotonic() - self._refreshed_at > self._ttl
            snapshot = self._snapshot
        if stale:
            self.refresh()
        return snapshot

    def refresh(self) -> bool:
        """Lanza un sondeo en segundo plano; ``False`` si ya hay uno en curso."""
        with self._lock:
            if self._running:
                return False
            self._running = True
        threading.Thread(target=self._run, name="dow-capabilities", daemon=True).start()
        return True

    def _run(self) -> None:
        try:
            capabilities = run_probe()
        except RuntimeError as exc:
            logger.warning(
                "Sondeo de capacidades fallido", extra={"exc_type": type(exc).__name__, "msg_detail": str(exc)}
            )
            with self._lock:
                previous = self._snapshot
                self._snapshot = CapabilitiesSnapshot("error", previous.checked_at, previous.capabilities)
                self._refreshed_at = time.monotonic()
                self._running = False
            return
        with self._lock:
            self._snapshot = CapabilitiesSnapshot("ok", datetime.now(UTC), capabilities)
            self._refreshed_at = time.monotonic()
            self._running = False


#: Caché única del proceso de la API.
capabilities_cache: Final = CapabilitiesCache()


if __name__ == "__main__":  # pragma: no cover - punto de entrada del subproceso
    logging.disable(logging.CRITICAL)
    print(json.dumps(asdict(collect())))
