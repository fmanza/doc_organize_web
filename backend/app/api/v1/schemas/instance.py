"""Capacidades e información de la instancia."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.api.v1.schemas._common import _Out


class CapabilitiesOut(BaseModel):
    """Capacidades de la instancia para convertir documentos."""

    gpu_support_installed: bool
    gpu_active: bool
    asr_installed: bool
    ffmpeg_installed: bool
    av_ready: bool
    libreoffice_installed: bool
    models_ready: bool = False
    picture_description_ready: bool = False
    gpu_ready: bool = False


class ScanOptionsAvailability(BaseModel):
    """Opciones de escaneo que algún worker vivo de su cola puede atender ahora (la API lo vuelve a comprobar)."""

    use_gpu: bool
    include_audio_video: bool
    use_picture_description: bool


class InstanceCapabilities(BaseModel):
    """Ficha de capacidades publicada por los workers: ``pending`` mientras el worker vivo no las ha calculado;
    ``no_worker`` si no hay worker vivo (con las últimas conocidas, si las hay)."""

    status: Literal["ok", "pending", "no_worker"]
    checked_at: datetime | None
    capabilities: CapabilitiesOut | None
    queues: list[str]
    capability_queues: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Por cada capacidad que algún worker vivo tiene, las colas de esos workers (p. ej. gpu_ready → gpu)",
    )
    doc_organize_version: str | None
    scan_options: ScanOptionsAvailability


class WorkerResources(BaseModel):
    """Memoria del contenedor del worker (cgroup), huecos de jobs y ajustes del escaneo, del último latido; ``None`` =
    desconocido (un worker anterior a la 1.1.0) o sin límite. ``memory_peak_bytes`` cuenta desde que arrancó el
    contenedor."""

    memory_limit_bytes: int | None = None
    memory_peak_bytes: int | None = None
    memory_current_bytes: int | None = None
    oom_kills: int | None = None
    slots: int | None = Field(default=None, description="Jobs simultáneos del worker (DOW_WORKER_CONCURRENCY)")
    scan_recycle_documents: int | None = None
    scan_document_timeout_seconds: int | None = Field(default=None, description="0 = sin límite")
    scan_io_retries: int | None = None
    scan_reuse_hashes: bool | None = None


class WorkerOut(_Out):
    """Worker registrado (solo admin), con su GPU y sus recursos (Fase 10)."""

    id: str
    queues: list[str]
    version: str
    doc_organize_version: str | None
    started_at: datetime
    heartbeat_at: datetime
    alive: bool
    capabilities_at: datetime | None
    gpu_ready: bool | None = None
    resources: WorkerResources | None = None
    running: int = Field(default=0, description="Ejecuciones que este worker tiene en marcha ahora")


class WorkerList(BaseModel):
    """Workers registrados."""

    items: list[WorkerOut]
