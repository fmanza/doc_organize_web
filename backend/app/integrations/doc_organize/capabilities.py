"""Capacidades de la instancia: GPU, audio/vídeo (Whisper + ffmpeg) y LibreOffice (rodeo de G12 y G15).

Hasta doc_organize 0.9.3, importar cualquier detector cargaba el paquete entero, con Docling (G15, resuelto en 0.10.0
con importaciones diferidas). Sigue sin haber un módulo de diagnóstico propio (G12, L-9b en 0.11.0) y el detector de
GPU importa torch, que tarda segundos en frío y ocupa memoria. Desde la Fase 3 lo ejecuta **cada worker** (la GPU que
importa es la de su contenedor) lanzando este módulo como subproceso
(``python -m app.integrations.doc_organize.capabilities``), que imprime el resultado en JSON; el worker lo publica en
``workers.capabilities`` y la API solo lee esa tabla.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final

logger = logging.getLogger(__name__)

#: Directorio que contiene el paquete ``app`` (``backend/`` en desarrollo, ``/app`` en la imagen).
_APP_PARENT: Final = Path(__file__).resolve().parents[3]
PROBE_TIMEOUT_SECONDS: Final = 180


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
        models_ready: Modelos base de Docling descargados (ADR-011): sin ellos fallan los PDF y las imágenes.
        picture_description_ready: Modelo de visión descargado (opción «describir imágenes»).
        gpu_ready: GPU activa y modelos de EasyOCR (opción «usar GPU»).
    """

    gpu_support_installed: bool
    gpu_active: bool
    asr_installed: bool
    ffmpeg_installed: bool
    av_ready: bool
    libreoffice_installed: bool
    models_ready: bool = False
    picture_description_ready: bool = False
    gpu_ready: bool = False


def collect() -> Capabilities:  # pragma: no cover - se ejecuta en el subproceso, con Docling y torch cargados
    """Llama a los detectores públicos de doc_organize (sin módulo de diagnóstico hasta L-9b, G12)."""
    from doc_organize import detect_av_status, detect_gpu_status, detect_office_status

    from app.core.config import get_settings
    from app.integrations.doc_organize.models import status as models_status

    gpu = detect_gpu_status()
    av = detect_av_status()
    office = detect_office_status()
    models = models_status(get_settings().models_dir)
    return Capabilities(
        gpu_support_installed=gpu.gpu_support_installed,
        gpu_active=gpu.gpu_active,
        asr_installed=av.asr_installed,
        ffmpeg_installed=av.ffmpeg_installed,
        av_ready=av.ready,
        libreoffice_installed=office.libreoffice_installed,
        models_ready=models.ready,
        picture_description_ready=models.ready and models.picture_description,
        gpu_ready=gpu.gpu_active and models.easyocr,
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


if __name__ == "__main__":  # pragma: no cover - punto de entrada del subproceso
    logging.disable(logging.CRITICAL)
    print(json.dumps(asdict(collect())))
