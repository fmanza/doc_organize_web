"""Revisar la clasificación (W5): motivos, decisiones y propuestas del revisor (W7)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Path, Query, status

from app.api.deps import Context, CurrentUser, DbSession, SettingsDep
from app.api.v1.context._shared import ERRORS, review_document_out
from app.api.v1.listing import LimitQuery, OffsetQuery
from app.api.v1.schemas import (
    DecisionIn,
    DecisionIssueOut,
    DecisionOut,
    DecisionRevokeIn,
    DecisionsOut,
    ProposalList,
    ProposalOut,
    ReviewItemOut,
    ReviewPage,
    ReviewReason,
)
from app.domain.context import decisions as decisions_service
from app.domain.context import service as context
from app.domain.projects import service as projects

router = APIRouter(tags=["context"])


def _decision_out(item: dict[str, Any]) -> DecisionOut:
    return DecisionOut.model_validate(item)


_DECISION_ERRORS: dict[int | str, dict[str, Any]] = {
    **ERRORS,
    403: {"description": "Rol insuficiente (editor)"},
    404: {"description": "Sin contexto, sin el documento o sin la decisión"},
    409: {"description": "Escritura en curso (write_locked) o carpeta .doc_organize que no es normal"},
    422: {"description": "Decisión no válida (decision_invalid) o destino de solo lectura"},
    503: {"description": "Ubicación no disponible"},
}


@router.get(
    "/projects/{project_id}/context/review",
    response_model=ReviewPage,
    summary="Cola de revisión de la clasificación",
    responses=ERRORS,
)
def get_review(
    project_id: int,
    user: CurrentUser,
    db: DbSession,
    settings: SettingsDep,
    reason: Annotated[ReviewReason | None, Query(description="Solo este motivo")] = None,
    q: Annotated[
        str | None,
        Query(max_length=200, description="Texto en el título, la carpeta, la ruta o la clave del documento"),
    ] = None,
    limit: LimitQuery = 50,
    offset: OffsetQuery = 0,
) -> ReviewPage:
    """Lo que habría que revisar según la última construcción (``review_queue``), por prioridad, con el documento y,
    si la hay, su decisión vigente (pendiente de aplicar hasta reconstruir). Con ``q`` (2.5.0), solo lo que coincide;
    el total y los recuentos por motivo también."""
    access = projects.get_access(db, project_id, user)
    rows, total, counts = decisions_service.review_items(
        db, access.project, reason=reason, limit=limit, offset=offset, q=q
    )
    active = {d["document_key"]: d for d in decisions_service.load(db, settings, access.project).active}
    axes = context.document_axes(db, access.project.id, [doc.seq for _, doc in rows if doc is not None])
    items = []
    for item, doc in rows:
        document = review_document_out(doc, axes.get(doc.seq)) if doc is not None else None
        decision = active.get(item.document_key)
        items.append(
            ReviewItemOut(
                id=item.id,
                document_key=item.document_key,
                reason=item.reason,
                priority=item.priority,
                axis=item.axis,
                value=item.value,
                confidence=item.confidence,
                detail=item.detail,
                document=document,
                decision=_decision_out(decision) if decision else None,
            )
        )
    return ReviewPage(items=items, total=total, counts=counts)


@router.get(
    "/projects/{project_id}/context/decisions",
    response_model=DecisionsOut,
    summary="Decisiones de personas",
    responses=ERRORS,
)
def get_decisions(project_id: int, user: CurrentUser, db: DbSession, settings: SettingsDep) -> DecisionsOut:
    """Vigentes (``.doc_organize/decisions.json``), historial de revocadas y las que la última construcción no aplicó
    (desfasadas y huérfanas)."""
    access = projects.get_access(db, project_id, user)
    found = decisions_service.load(db, settings, access.project)
    return DecisionsOut(
        decisions=[_decision_out(d) for d in found.active],
        revoked=[_decision_out(d) for d in found.revoked],
        stale=[DecisionIssueOut.model_validate(i) for i in found.stale],
        orphan=[DecisionIssueOut.model_validate(i) for i in found.orphan],
        applied=found.applied,
    )


@router.post(
    "/projects/{project_id}/context/decisions",
    response_model=DecisionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Decidir sobre un documento",
    responses=_DECISION_ERRORS,
)
def post_decision(
    project_id: int, body: DecisionIn, user: CurrentUser, db: DbSession, settings: SettingsDep, ctx: Context
) -> DecisionOut:
    """Confirmar la clasificación, fijar los valores de un eje (del catálogo), sacar el documento del contexto o
    marcarlo como versión vigente. Se aplica en la siguiente construcción; propietario o editor; auditado."""
    access = projects.get_access(db, project_id, user, min_role="editor")
    saved = decisions_service.decide(
        db,
        settings,
        access.project,
        document_key=body.document_key,
        action=body.action,
        axes=body.axes,
        reason=body.reason,
        actor=user,
        ctx=ctx,
    )
    return _decision_out(saved)


@router.post(
    "/projects/{project_id}/context/decisions/{decision_id}/revoke",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revocar una decisión",
    responses=_DECISION_ERRORS,
)
def revoke_decision(
    project_id: int,
    decision_id: Annotated[str, Path(min_length=1, max_length=64)],
    body: DecisionRevokeIn,
    user: CurrentUser,
    db: DbSession,
    settings: SettingsDep,
    ctx: Context,
) -> None:
    """La decisión deja de aplicarse en la siguiente construcción y pasa al historial."""
    access = projects.get_access(db, project_id, user, min_role="editor")
    decisions_service.revoke(db, settings, access.project, decision_id, reason=body.reason, actor=user, ctx=ctx)


@router.get(
    "/projects/{project_id}/context/review/proposals",
    response_model=ProposalList,
    summary="Propuestas pendientes del revisor",
    responses=ERRORS,
)
def get_proposals(project_id: int, user: CurrentUser, db: DbSession) -> ProposalList:
    """Las propuestas del revisor (``context_review_agent``) que nadie ha aceptado ni descartado, con su documento."""
    access = projects.get_access(db, project_id, user)
    rows = decisions_service.list_proposals(db, access.project)
    axes = context.document_axes(db, access.project.id, [doc.seq for _, doc in rows if doc is not None])
    items = []
    for proposal, doc in rows:
        document = review_document_out(doc, axes.get(doc.seq)) if doc is not None else None
        items.append(
            ProposalOut(
                id=proposal.id,
                document_key=proposal.document_key,
                action=proposal.action,
                axes=proposal.axes or {},
                rationale=proposal.rationale,
                evidence=proposal.evidence,
                created_at=proposal.created_at,
                run_id=proposal.run_id,
                proposal_key=proposal.proposal_key,
                document=document,
            )
        )
    return ProposalList(items=items)


@router.post(
    "/projects/{project_id}/context/review/proposals/{proposal_id}/accept",
    response_model=DecisionOut,
    summary="Aceptar una propuesta del revisor",
    responses={**_DECISION_ERRORS, 404: {"description": "Sin la propuesta (proposal_not_found) o sin el documento"}},
)
def accept_proposal(
    project_id: int, proposal_id: int, user: CurrentUser, db: DbSession, settings: SettingsDep, ctx: Context
) -> DecisionOut:
    """La propuesta se guarda como decisión de quien la acepta (se aplica al reconstruir). Propietario o editor."""
    access = projects.get_access(db, project_id, user, min_role="editor")
    return _decision_out(
        decisions_service.accept_proposal(db, settings, access.project, proposal_id, actor=user, ctx=ctx)
    )


@router.post(
    "/projects/{project_id}/context/review/proposals/{proposal_id}/discard",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Descartar una propuesta del revisor",
    responses={**_DECISION_ERRORS, 404: {"description": "Sin la propuesta (proposal_not_found)"}},
)
def discard_proposal(
    project_id: int, proposal_id: int, user: CurrentUser, db: DbSession, settings: SettingsDep, ctx: Context
) -> None:
    """No se aplica nada; la propuesta deja de estar pendiente. Propietario o editor."""
    access = projects.get_access(db, project_id, user, min_role="editor")
    decisions_service.discard_proposal(db, settings, access.project, proposal_id, actor=user, ctx=ctx)
