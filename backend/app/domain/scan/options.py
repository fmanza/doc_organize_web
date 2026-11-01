"""Validación de las opciones de un escaneo contra las capacidades que publican los workers (WB-4.1).

La API no detecta nada (no importa doc_organize, G15): lee ``workers.capabilities`` de los workers vivos de la cola
que atenderá el run. Una opción solo se acepta si algún worker de esa cola confirma que puede con ella; el worker lo
vuelve a comprobar al empezar.
"""

from __future__ import annotations

from typing import Any, Final

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import RunQueue
from app.domain.runs.operations import ScanParams, queue_for
from app.domain.runs.workers import is_alive, list_workers
from app.domain.scan.errors import OptionUnavailableError

#: Opción de ``ScanParams`` → capacidad del worker que la permite.
OPTION_CAPABILITY: Final = {
    "use_gpu": "gpu_ready",
    "include_audio_video": "av_ready",
    "use_picture_description": "picture_description_ready",
}
_LABELS: Final = {
    "use_gpu": "GPU",
    "include_audio_video": "audio y vídeo",
    "use_picture_description": "descripción de imágenes",
}


def queue_capabilities(db: Session, settings: Settings, queue: RunQueue) -> list[dict[str, Any]]:
    """Capacidades publicadas por los workers vivos que atienden ``queue``."""
    return [
        w.capabilities
        for w in list_workers(db)
        if queue in w.queues and is_alive(w, settings) and w.capabilities is not None
    ]


def missing_options(params: ScanParams, capabilities: list[dict[str, Any]]) -> list[str]:
    """Opciones activadas en ``params`` que ningún worker de ``capabilities`` puede atender."""
    return [
        option
        for option, capability in OPTION_CAPABILITY.items()
        if getattr(params, option) and not any(bool(caps.get(capability)) for caps in capabilities)
    ]


def check_options(db: Session, settings: Settings, params: ScanParams) -> None:
    """Comprueba las opciones del escaneo contra los workers de su cola.

    Raises:
        OptionUnavailableError: Ningún worker vivo de la cola confirma alguna de las opciones activadas.
    """
    if params.dry_run:
        return
    missing = missing_options(params, queue_capabilities(db, settings, queue_for(params)))
    if missing:
        names = ", ".join(_LABELS[m] for m in missing)
        raise OptionUnavailableError(f"Esta instancia no puede atender ahora: {names}.")


def available_options(db: Session, settings: Settings) -> dict[str, bool]:
    """Si cada opción, activada sola, la puede atender algún worker vivo de la cola a la que iría."""
    cpu = queue_capabilities(db, settings, "cpu")
    gpu = queue_capabilities(db, settings, "gpu")
    return {
        option: any(bool(caps.get(capability)) for caps in (gpu if option == "use_gpu" else cpu))
        for option, capability in OPTION_CAPABILITY.items()
    }
