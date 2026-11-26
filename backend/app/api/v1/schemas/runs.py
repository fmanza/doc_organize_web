"""Ejecuciones (cola, progreso y resultados)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.api.v1.schemas._common import _Out
from app.api.v1.schemas.projects import Operation, RunStatus


class ArtifactOut(_Out):
    """Fichero de un run, descargable mientras no lo purgue la retención."""

    id: int
    name: str
    kind: Literal["log", "output", "report"]
    size_bytes: int
    content_type: str
    created_at: datetime


class RunProgress(BaseModel):
    """Último progreso publicado."""

    phase: str
    processed: int
    total: int | None = None
    current: str | None = None


class ContextLeftoverOut(BaseModel):
    """Contexto que quedó en disco sin guardarse (construcción interrumpida, 2.1), o ninguno."""

    output_folder_name: str | None = Field(
        description="Carpeta reorganizada del context.json que hay en el destino; null si no hay restos"
    )


class AiUsageRowOut(BaseModel):
    """Consumo de IA de una ejecución en una tarea (web 2.1). Sin coste: el proxy no lo da por llamada."""

    task: str
    model: str | None
    calls: int = Field(description="Documentos enviados (pasos, en los agentes; textos embebidos, en embed)")
    cached: int = Field(description="Resueltos con la caché de resultados de IA, sin llamar al modelo")
    failed: int
    prompt_tokens: int
    completion_tokens: int
    tokens_estimated: bool = Field(description="Tokens estimados (agentes, si el proxy no los informa)")


class RunOut(BaseModel):
    """Ejecución con su estado, progreso, resultado y artefactos."""

    id: str
    project_id: int | None
    project_name: str | None
    operation: Operation
    queue: Literal["cpu", "gpu"]
    status: RunStatus
    is_write: bool
    params: dict[str, Any]
    progress: RunProgress | None
    result: dict[str, Any] | None
    error_code: str | None
    error_message: str | None
    cancel_requested: bool
    created_by_username: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    workspace_purged: bool
    artifacts: list[ArtifactOut]
    can_cancel: bool
    ai_usage: list[AiUsageRowOut] = Field(
        default_factory=list, description="Consumo de IA por tarea (solo en el detalle de una ejecución; 2.1)"
    )


class RunPage(BaseModel):
    """Página del historial de ejecuciones."""

    items: list[RunOut]
    total: int
