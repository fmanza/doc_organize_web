"""Ajustes y tareas de IA (Fase 8)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

#: doc_organize 2.0 (W2): una familia ``litellm`` para todas las tareas de IA (migración ``0016``) y las dos de uso.
AiFamilyKey = Literal["litellm", "litellm_usage"]
AiTaskKey = Literal["classify", "enrich", "taxonomy_design", "agent", "embed", "dedup"]


class AiFieldOut(BaseModel):
    """Campo de una familia de IA. ``value`` solo en los no secretos; ``hint`` («…ab12» o «***») solo en los secretos."""

    name: str
    env_var: str | None = Field(description="Variable de entorno equivalente; null si el campo no tiene")
    secret: bool
    required: bool
    source: Literal["db", "env", "none"]
    value: str | None
    hint: str | None
    undecryptable: bool = Field(description="Hay un valor guardado que no se descifra con las claves actuales")
    task: AiTaskKey | None = Field(
        default=None, description="Tarea del campo en la familia litellm (modelo, clave o presupuesto); null = de todas"
    )


class AiFamilyOut(BaseModel):
    key: AiFamilyKey
    configured: bool = Field(description="Tiene todos sus campos obligatorios")
    fields: list[AiFieldOut]


class AiSettingsOut(BaseModel):
    """Configuración de IA de la instancia, sin ningún secreto."""

    encryption_configured: bool
    families: list[AiFamilyOut]


class AiFamilyUpdate(BaseModel):
    """Campos que cambian: ausente = no se toca; ``null`` o ``""`` = borrar el valor guardado (vuelve al entorno)."""

    model_config = ConfigDict(extra="forbid")

    fields: dict[Annotated[str, Field(max_length=32)], Annotated[str, Field(max_length=4096)] | None] = Field(
        max_length=16
    )


class AiTestIn(BaseModel):
    """«Probar conexión»: valores del formulario que sustituyen a los efectivos (ausente = el efectivo; ``null`` o ``""``
    = sin valor). No se guarda nada."""

    model_config = ConfigDict(extra="forbid")

    fields: dict[Annotated[str, Field(max_length=32)], Annotated[str, Field(max_length=4096)] | None] = Field(
        default_factory=dict, max_length=16
    )
    model_check: bool = Field(
        default=False,
        description="Enviar también una petición mínima al modelo (gasta unos pocos tokens; solo familias con modelo)",
    )
    task: AiTaskKey = Field(default="classify", description="Tarea cuyo modelo se prueba (familia litellm)")


class AiTestOut(BaseModel):
    """Resultado de «Probar conexión»: solo un código, nunca el cuerpo de lo que respondió el servidor."""

    ok: bool
    error: Literal["ai_auth", "ai_connection", "ai_error", "ai_model"] | None = Field(
        description="Credencial rechazada, sin conexión o timeout, otro error, o el modelo no respondió"
    )
    model_access: Literal["ok", "denied", "unknown"] = Field(
        description="Si la clave de LiteLLM tiene acceso al modelo según /key/info (unknown si no lo dice)"
    )
    model_checked: bool = Field(description="Si se envió la petición al modelo")
    task: AiTaskKey | None = Field(default=None, description="Tarea cuyo modelo se probó (familia litellm)")
    response_format: Literal["json_schema", "json_object"] | None = Field(
        default=None, description="Formato con el que respondió el modelo: json_schema si admite la salida estricta"
    )
    model: str | None = Field(default=None, description="Modelo (alias del proxy) que se probó (2.2)")
    served_model: str | None = Field(
        default=None, description="Modelo que dice la respuesta que contestó, detrás del alias (2.2), si lo dice"
    )
    dimension: int | None = Field(
        default=None, description="Dimensión de los vectores en las tareas de embeddings (2.2)"
    )
    elapsed_ms: int
    tested_at: AwareDatetime


class AiStatusOut(BaseModel):
    """Qué familias y qué tareas de IA están configuradas (para cualquier usuario, sin valores)."""

    families: dict[str, bool]
    tasks: dict[str, bool] = Field(
        default_factory=dict, description="Tarea de IA (doc_organize 2.0) → si se puede usar"
    )


class AiUsageItemOut(BaseModel):
    date: str
    product: str
    sku: str | None
    quantity: float
    unit_type: str
    cost_usd: float | None


class AiKeyBudgetOut(BaseModel):
    """Gasto y presupuesto de la clave según ``/key/info`` del proxy (lo que diga; ``None`` si no lo dice)."""

    spend: float | None
    max_budget: float | None
    remaining: float | None
    budget_reset_at: str | None


class AiUsageSourceOut(BaseModel):
    """Uso de una fuente en el periodo actual, o por qué no hay (sin configurar o ``error``)."""

    source: Literal["litellm"]
    configured: bool
    fetched_at: datetime | None
    cached: bool
    period_start: str | None
    period_end: str | None
    total_cost_usd: float | None
    items: list[AiUsageItemOut]
    budget: AiKeyBudgetOut | None = None
    error: Literal["ai_auth", "ai_connection", "ai_error"] | None


class AiUsageTotalsOut(BaseModel):
    """Totales de consumo de IA (registro propio de la web, 2.1)."""

    runs: int
    calls: int
    cached: int
    failed: int
    prompt_tokens: int
    completion_tokens: int
    tokens_estimated: bool


class AiUsageGroupOut(AiUsageTotalsOut):
    """Totales de una tarea, un modelo o un proyecto (``key``: la tarea, el modelo o el id del proyecto)."""

    key: str
    label: str | None = Field(default=None, description="Nombre del proyecto (en «por proyecto»)")
    project_id: int | None = None


class AiUsageDayOut(AiUsageTotalsOut):
    """Totales de un día en la zona horaria pedida."""

    day: date


class AiUsageRunOut(AiUsageTotalsOut):
    """Una de las ejecuciones que más tokens gastaron."""

    run_id: str | None
    created_at: datetime
    operation: str
    project_id: int | None
    project_name: str | None


class AiUsageLocalOut(BaseModel):
    """Consumo registrado por la web en el periodo (``ai_usage``), agrupado por día en ``timezone``."""

    period: Literal["7d", "30d", "month", "all"]
    timezone: str
    start: datetime | None
    end: datetime
    totals: AiUsageTotalsOut
    by_task: list[AiUsageGroupOut]
    by_model: list[AiUsageGroupOut]
    by_project: list[AiUsageGroupOut]
    by_day: list[AiUsageDayOut]
    top_runs: list[AiUsageRunOut]


class AiUsageOut(BaseModel):
    sources: list[AiUsageSourceOut]
    local: AiUsageLocalOut | None = Field(default=None, description="Consumo por ejecución registrado por la web (2.1)")
