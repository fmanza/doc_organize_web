"""Calidad del contexto (W5)."""

from __future__ import annotations

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.domain.runs.results import ContextAuditResult, ContextDryRunResult, ContextEvaluateResult


class GoldOut(BaseModel):
    """Referencia en Excel del proyecto (sin el contenido): de dónde se leyó y qué tiene."""

    filename: str
    sheet: str
    document_column: str
    columns: dict[str, str]
    labels: int = Field(description="Documentos etiquetados")
    axes: list[str] = Field(description="Ejes con etiquetas")
    uploaded_at: str
    uploaded_by: str | None = None


class _QualityRunOut(BaseModel):
    """El último run terminado de una comprobación de calidad, con su resultado."""

    run_id: str
    finished_at: AwareDatetime | None


class QualityEvaluationOut(_QualityRunOut):
    """La última evaluación terminada (``context_evaluate``)."""

    result: ContextEvaluateResult


class QualityDryRunOut(_QualityRunOut):
    """La última comparación terminada (``context_dry_run``)."""

    result: ContextDryRunResult


class QualityAuditOut(_QualityRunOut):
    """El último informe del auditor terminado (``context_audit``)."""

    result: ContextAuditResult


class QualityOut(BaseModel):
    """Calidad de la clasificación del proyecto: la referencia y la última evaluación y comparación terminadas."""

    gold: GoldOut | None = None
    decisions_available: bool = Field(description="Hay decisiones de personas con las que hacer una referencia")
    evaluation: QualityEvaluationOut | None = None
    dry_run: QualityDryRunOut | None = None
    audit: QualityAuditOut | None = Field(default=None, description="Último informe del auditor (W7)")


class DiagnosticsIn(BaseModel):
    """Diagnóstico del entorno (W4): ``check_ai`` prueba también los modelos de IA configurados (gasta unos tokens)."""

    model_config = ConfigDict(extra="forbid")

    check_ai: bool = False


class DiagnosticCheckOut(BaseModel):
    """Una comprobación de ``check_environment``: ``ok``, ``warning`` o ``error``, con qué hacer si no es ``ok``."""

    name: str
    status: Literal["ok", "warning", "error"]
    detail: str
    remedy: str | None = None


class DiagnosticsOut(BaseModel):
    """Resultado del diagnóstico del entorno, sin claves, URL del proxy ni rutas del contenedor."""

    ok: bool
    checked_at: str
    checks: list[DiagnosticCheckOut]
