"""Registro de auditoría."""

from __future__ import annotations

from datetime import datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.api.v1.schemas._common import _Out


class AuditEntryOut(_Out):
    """Evento de auditoría."""

    id: int
    ts: datetime
    actor_user_id: int | None
    actor_username: str | None
    action: str
    outcome: str
    target_type: str | None
    target_id: str | None
    ip: str | None
    details: dict[str, object] | None


class AuditPage(BaseModel):
    """Página de auditoría."""

    items: list[AuditEntryOut]
    total: int


class AuditPurgeIn(BaseModel):
    """Borrar la auditoría del tenant activo en ``[since, until)`` (web 1.2.0, solo el admin de instancia).

    Primero con ``dry_run`` (cuenta las entradas); después sin él y con ``confirm_count`` igual a esa cuenta.
    """

    model_config = ConfigDict(extra="forbid")

    since: AwareDatetime = Field(description="Desde (incluido), ISO 8601 con zona")
    until: AwareDatetime = Field(description="Hasta (excluido), como tarde hoy a las 00:00 UTC")
    dry_run: bool = True
    confirm_count: int | None = Field(default=None, ge=0, description="Entradas que mostró la vista previa")


class AuditPurgeOut(BaseModel):
    """Entradas del rango (``matched``) y las borradas (``deleted``: 0 en la vista previa)."""

    matched: int
    deleted: int
