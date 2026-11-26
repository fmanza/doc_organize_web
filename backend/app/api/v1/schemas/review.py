"""Revisión de la clasificación (W5) y propuestas del revisor (W7)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.api.v1.schemas.context import AxisValueOut

# --- W5: revisar la clasificación -------------------------------------------------------------------------------------

ReviewReason = Literal[
    "stale_decision",
    "unclassified",
    "rules_ai_disagreement",
    "unverified_evidence",
    "low_confidence",
    "unconfirmed_version",
]


class ReviewDocumentOut(BaseModel):
    """El documento de un motivo de revisión, con sus valores por eje y su versión."""

    seq: int
    title: str
    folder: str
    path: str
    domain_slug: str | None
    output_path: str | None = None
    version: str | None = None
    version_group: str | None = None
    is_current: bool | None = None
    axes: dict[str, list[AxisValueOut]] = {}


class DecisionOut(BaseModel):
    """Una decisión de una persona (``ClassificationDecision``): vigente o, con ``revoked_at``, del historial."""

    id: str
    document_key: str
    action: Literal["confirm", "set_axis", "exclude", "set_current_version"]
    axes: dict[str, list[str]] = {}
    author: str | None = None
    decided_at: str
    reason: str | None = None
    source_sha256: str | None = None
    revoked_at: str | None = None
    revoked_by: str | None = None
    revoke_reason: str | None = None


class ReviewItemOut(BaseModel):
    """Un motivo para revisar un documento (``review_queue``), con el documento y su decisión vigente, si la hay."""

    id: int
    document_key: str
    reason: ReviewReason
    priority: int
    axis: str | None = None
    value: str | None = None
    confidence: float | None = None
    detail: str | None = None
    document: ReviewDocumentOut | None = None
    decision: DecisionOut | None = Field(
        default=None, description="Decisión vigente del documento (se aplica en la siguiente construcción)"
    )


class ReviewPage(BaseModel):
    items: list[ReviewItemOut]
    total: int
    counts: dict[str, int] = Field(default_factory=dict, description="Motivos de revisión → cuántos hay")


class DecisionIssueOut(BaseModel):
    """Una decisión que la última construcción no aplicó, y por qué."""

    decision_id: str
    document_key: str
    reason: str
    detail: str | None = None


class DecisionsOut(BaseModel):
    """Decisiones del proyecto: vigentes, historial y las no aplicadas en la última construcción."""

    decisions: list[DecisionOut]
    revoked: list[DecisionOut]
    stale: list[DecisionIssueOut] = []
    orphan: list[DecisionIssueOut] = []
    applied: int = 0


class DecisionIn(BaseModel):
    """Una decisión sobre un documento del contexto (se aplica en la siguiente construcción).

    ``confirm``: los valores de los ejes que se confirman. ``set_axis``: un eje y sus valores. ``exclude`` y
    ``set_current_version``: sin ejes.
    """

    model_config = ConfigDict(extra="forbid")

    document_key: str = Field(min_length=1, max_length=4096)
    action: Literal["confirm", "set_axis", "exclude", "set_current_version"]
    axes: dict[Annotated[str, Field(max_length=41)], list[Annotated[str, Field(min_length=1, max_length=128)]]] = Field(
        default_factory=dict, max_length=10
    )
    reason: str | None = Field(default=None, max_length=500)


class DecisionRevokeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=500)


# --- W7: propuestas del revisor ---------------------------------------------------------------------------------------


class ProposalOut(BaseModel):
    """Una propuesta pendiente del revisor (``ReviewAgent``): no se aplica hasta que una persona la acepta."""

    id: int
    document_key: str
    action: Literal["confirm", "set_axis", "exclude", "set_current_version"]
    axes: dict[str, list[str]] = {}
    rationale: str | None = None
    evidence: str | None = None
    created_at: datetime
    run_id: str | None = None
    proposal_key: str | None = Field(default=None, description="``ReviewProposal.id`` de doc_organize")
    document: ReviewDocumentOut | None = None


class ProposalList(BaseModel):
    items: list[ProposalOut]
