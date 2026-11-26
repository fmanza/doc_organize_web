"""Revisar la clasificación (W5, doc_organize 2.0 F6): la cola de revisión de la última construcción y las decisiones
de personas.

- La **cola** (``review_queue``) la calcula la construcción en el worker y queda en ``context_review_items``: leerla no
  toca el destino.
- Las **decisiones** viven donde las lee doc_organize, en ``<proyecto>/.doc_organize/decisions.json``
  (``ClassificationDecisionStore``: escritura atómica, con bloqueo e historial de revocadas). Se aplican en la siguiente
  construcción, antes de la IA; el autor es el usuario de la web.
- Decidir o revocar: propietario o editor, con el destino de lectura y escritura y sin escrituras en curso; cada
  decisión se audita. Se valida contra el catálogo del contexto (ejes y valores de ``taxonomy_axes``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import ContextDocument, ContextReviewItem, Project, User
from app.domain.context import manifest_versions
from app.domain.context.errors import (
    DecisionDocumentNotFoundError,
    DecisionInvalidError,
    DecisionNotFoundError,
    ProfileReplacedError,
)
from app.domain.context.profile import _regular
from app.domain.context.service import _check_writable, _output_root, get_context
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction, RequestContext
from app.domain.listing import apply_search
from app.domain.locations.errors import LocationUnavailableError
from app.domain.locations.paths import run_with_timeout
from app.integrations.doc_organize import context as library

DecisionAction = Literal["confirm", "set_axis", "exclude", "set_current_version"]
MAX_REASON: Final = 500


@dataclass(frozen=True)
class Decisions:
    """Decisiones del proyecto: vigentes, historial y las que la última construcción no aplicó."""

    active: list[dict[str, Any]]
    revoked: list[dict[str, Any]]
    stale: list[dict[str, Any]] = field(default_factory=list)
    orphan: list[dict[str, Any]] = field(default_factory=list)
    applied: int = 0


def _store_dir_is_safe(settings: Settings, root: Path) -> None:
    """La carpeta ``.doc_organize`` (si existe) es una carpeta normal: nunca se escribe a través de un enlace.

    Los ``lstat`` van con límite de tiempo, como el resto de la E/S del destino (un montaje de red caído no bloquea la
    petición).

    Raises:
        ProfileReplacedError: No lo es.
        LocationUnavailableError: El destino no responde o no deja leer la carpeta.
    """
    store = library.decisions_file(root)

    def check() -> None:
        _regular(store.parent, "dir")
        _regular(store, "file")

    try:
        run_with_timeout(check, settings.location_probe_timeout_seconds)
    except OSError:
        raise LocationUnavailableError("No se pudo comprobar la carpeta de decisiones del proyecto.") from None


def load(db: Session, settings: Settings, project: Project) -> Decisions:
    """Decisiones vigentes y revocadas (del destino) y las no aplicadas de la última construcción (de la BD)."""
    root = _output_root(settings, project)
    _store_dir_is_safe(settings, root)
    try:
        active, revoked = run_with_timeout(
            lambda: library.load_decisions(root), settings.location_probe_timeout_seconds
        )
    except (OSError, ValueError):
        raise LocationUnavailableError("No se pudieron leer las decisiones del proyecto.") from None
    row = get_context_row(db, project)
    return Decisions(
        active=active,
        revoked=list(reversed(revoked)),
        stale=list(row.stale_decisions) if row else [],
        orphan=list(row.orphan_decisions) if row else [],
        applied=int(row.decisions_applied) if row else 0,
    )


def get_context_row(db: Session, project: Project) -> Any:
    """La proyección del contexto, o ``None`` si no hay."""
    from app.db.models import ProjectContext

    return db.get(ProjectContext, project.id)


def _validate_axes(
    row: Any, document: ContextDocument, action: DecisionAction, axes: dict[str, list[str]]
) -> dict[str, list[str]]:
    """Valores por eje validados contra el catálogo del contexto (``taxonomy_axes``).

    Raises:
        DecisionInvalidError: Eje o valor que no está, varios valores en un eje que no los admite, o la acción no
            casa con los ejes.
    """
    catalog = {axis["key"]: axis for axis in row.taxonomy_axes}
    if action in ("exclude", "set_current_version"):
        if axes:
            raise DecisionInvalidError(f"«{action}» no lleva ejes.")
        if action == "set_current_version" and not document.version_group:
            raise DecisionInvalidError("El documento no está en ningún grupo de versiones.")
        return {}
    if action == "set_axis" and len(axes) != 1:
        raise DecisionInvalidError("«set_axis» decide exactamente un eje.")
    if action == "confirm" and not axes:
        raise DecisionInvalidError("«confirm» necesita los valores de los ejes que se confirman.")
    clean: dict[str, list[str]] = {}
    for key, values in axes.items():
        axis = catalog.get(key)
        if axis is None:
            raise DecisionInvalidError(f"El eje «{key}» no está en el contexto.")
        allowed = {value["slug"] for value in axis.get("values", [])}
        unknown = [value for value in values if value not in allowed]
        if unknown:
            raise DecisionInvalidError(f"«{', '.join(unknown)}» no es un valor del eje «{axis['name']}».")
        unique = list(dict.fromkeys(values))
        if axis.get("organizes") and len(unique) != 1:
            raise DecisionInvalidError(f"El eje «{axis['name']}» organiza carpetas: lleva exactamente un valor.")
        if not axis.get("multiple") and len(unique) > 1:
            raise DecisionInvalidError(f"El eje «{axis['name']}» admite un solo valor.")
        clean[key] = unique
    return clean


def decide(
    db: Session,
    settings: Settings,
    project: Project,
    *,
    document_key: str,
    action: DecisionAction,
    axes: dict[str, list[str]],
    reason: str | None,
    actor: User,
    ctx: RequestContext,
) -> dict[str, Any]:
    """Guarda una decisión sobre ``document_key`` (se aplica en la siguiente construcción) y la audita.

    Raises:
        ContextNotFoundError: Sin contexto construido.
        DecisionDocumentNotFoundError: El documento no está en el contexto.
        DecisionInvalidError: No casa con el catálogo o con la acción.
        DestinationReadOnlyError, WriteLockedError, ProfileReplacedError, LocationUnavailableError.
    """
    row = get_context(db, project)
    document = db.scalar(
        select(ContextDocument).where(
            ContextDocument.project_id == project.id, ContextDocument.document_key == document_key
        )
    )
    if document is None:
        raise DecisionDocumentNotFoundError("El documento no está en el contexto: reconstruye antes.")
    clean = _validate_axes(row, document, action, axes)
    _check_writable(db, project)
    root = _output_root(settings, project)
    _store_dir_is_safe(settings, root)
    with manifest_versions.project_lock(project.id):
        try:
            saved = run_with_timeout(
                lambda: library.add_decision(
                    root,
                    document_key=document_key,
                    action=action,
                    axes=clean,
                    author=actor.username,
                    reason=(reason or "").strip()[:MAX_REASON] or None,
                    source_sha256=document.source_sha256,
                ),
                settings.location_probe_timeout_seconds,
            )
        except library.DecisionInvalidError as exc:
            raise DecisionInvalidError(str(exc)) from None
        except OSError:
            raise LocationUnavailableError("No se pudo guardar la decisión en el destino.") from None
    audit.record(
        db,
        action=AuditAction.PROJECT_DECISION_ADD,
        ctx=ctx,
        actor_id=actor.id,
        target_type="project",
        target_id=project.id,
        details={"decision_id": saved["id"], "document_key": document_key, "action": action, "axes": clean},
    )
    db.commit()
    return saved


def revoke(
    db: Session,
    settings: Settings,
    project: Project,
    decision_id: str,
    *,
    reason: str | None,
    actor: User,
    ctx: RequestContext,
) -> None:
    """Revoca una decisión vigente (pasa al historial con quién y por qué) y lo audita.

    Raises:
        DecisionNotFoundError: No hay ninguna vigente con ese ``id``.
        DestinationReadOnlyError, WriteLockedError, ProfileReplacedError, LocationUnavailableError.
    """
    _check_writable(db, project)
    root = _output_root(settings, project)
    _store_dir_is_safe(settings, root)
    with manifest_versions.project_lock(project.id):
        try:
            found = run_with_timeout(
                lambda: library.revoke_decision(
                    root,
                    decision_id,
                    author=actor.username,
                    reason=(reason or "").strip()[:MAX_REASON] or None,
                ),
                settings.location_probe_timeout_seconds,
            )
        except OSError:
            raise LocationUnavailableError("No se pudo revocar la decisión en el destino.") from None
    if not found:
        raise DecisionNotFoundError()
    audit.record(
        db,
        action=AuditAction.PROJECT_DECISION_REVOKE,
        ctx=ctx,
        actor_id=actor.id,
        target_type="project",
        target_id=project.id,
        details={"decision_id": decision_id},
    )
    db.commit()


def review_items(
    db: Session, project: Project, *, reason: str | None, limit: int, offset: int, q: str | None = None
) -> tuple[list[tuple[ContextReviewItem, ContextDocument | None]], int, dict[str, int]]:
    """Página de la cola de revisión (por prioridad), con su documento, el total y el recuento por motivo.

    ``q`` (2.5.0) filtra por nombre sin distinguir mayúsculas: el título, la carpeta o la ruta del documento, o la clave
    (la única que tiene una decisión de un documento que ya no está). El total y los recuentos por motivo, también los
    de las propuestas del revisor, cuentan solo lo que coincide.

    Raises:
        ContextNotFoundError: Sin contexto construido.
    """
    from app.db.models import ContextReviewProposal

    get_context(db, project)
    joined = (ContextDocument.project_id == ContextReviewItem.project_id) & (
        ContextDocument.seq == ContextReviewItem.seq
    )
    columns = (ContextReviewItem.document_key, ContextDocument.title, ContextDocument.folder, ContextDocument.path)

    def _filtered(query: Any) -> Any:  # un Select de una o dos entidades (SQLAlchemy 2.1 tipa cada columna)
        return apply_search(query.outerjoin(ContextDocument, joined), q, columns).where(
            ContextReviewItem.project_id == project.id
        )

    by_reason = [ContextReviewItem.reason == reason] if reason else []
    total = db.scalar(_filtered(select(func.count()).select_from(ContextReviewItem)).where(*by_reason)) or 0
    rows = db.execute(
        _filtered(select(ContextReviewItem, ContextDocument).select_from(ContextReviewItem))
        .where(*by_reason)
        .order_by(ContextReviewItem.priority, ContextReviewItem.id)
        .limit(limit)
        .offset(offset)
    ).all()
    counts = dict(
        db.execute(
            _filtered(select(ContextReviewItem.reason, func.count()).select_from(ContextReviewItem)).group_by(
                ContextReviewItem.reason
            )
        ).all()
    )
    pending = db.scalar(
        apply_search(
            select(func.count())
            .select_from(ContextReviewProposal)
            .where(ContextReviewProposal.project_id == project.id, ContextReviewProposal.status == "pending"),
            q,
            (ContextReviewProposal.document_key,),
        )
    )
    result = {k: int(v) for k, v in counts.items()}
    if pending:
        result["reviewer_proposal"] = int(pending)
    return [(item, document) for item, document in rows], int(total), result


__all__ = [
    "Decisions",
    "ProfileReplacedError",
    "accept_proposal",
    "decide",
    "discard_proposal",
    "list_proposals",
    "load",
    "review_items",
    "revoke",
]


# --- propuestas del revisor (W7) --------------------------------------------------------------------------------------


def list_proposals(db: Session, project: Project) -> list[tuple[Any, ContextDocument | None]]:
    """Propuestas pendientes del revisor, con su documento del contexto (si sigue estando)."""
    from app.db.models import ContextReviewProposal

    rows = db.execute(
        select(ContextReviewProposal, ContextDocument)
        .outerjoin(
            ContextDocument,
            (ContextDocument.project_id == ContextReviewProposal.project_id)
            & (ContextDocument.document_key == ContextReviewProposal.document_key),
        )
        .where(ContextReviewProposal.project_id == project.id, ContextReviewProposal.status == "pending")
        .order_by(ContextReviewProposal.id)
    ).all()
    return [(proposal, document) for proposal, document in rows]


def _pending(db: Session, project: Project, proposal_id: int) -> Any:
    from app.db.models import ContextReviewProposal
    from app.domain.context.errors import ProposalNotFoundError

    proposal = db.get(ContextReviewProposal, proposal_id)
    if proposal is None or proposal.project_id != project.id or proposal.status != "pending":
        raise ProposalNotFoundError()
    return proposal


def accept_proposal(
    db: Session, settings: Settings, project: Project, proposal_id: int, *, actor: User, ctx: RequestContext
) -> dict[str, Any]:
    """Acepta una propuesta del revisor: se guarda como decisión de ``actor`` (validada como cualquier otra) y queda
    ``accepted``. Se audita (la decisión, además, como ``project.decision_add``).

    Raises:
        ProposalNotFoundError, DecisionDocumentNotFoundError, DecisionInvalidError y los de ``decide``.
    """
    from app.db.models import utcnow

    proposal = _pending(db, project, proposal_id)
    reason = f"Propuesta del revisor: {proposal.rationale}" if proposal.rationale else "Propuesta del revisor"
    saved = decide(
        db,
        settings,
        project,
        document_key=proposal.document_key,
        action=proposal.action,
        axes=dict(proposal.axes or {}),
        reason=reason,
        actor=actor,
        ctx=ctx,
    )
    proposal.status = "accepted"
    proposal.decided_by = actor.id
    proposal.decided_at = utcnow()
    proposal.decision_id = str(saved["id"])
    audit.record(
        db,
        action=AuditAction.PROJECT_PROPOSAL_ACCEPT,
        ctx=ctx,
        actor_id=actor.id,
        target_type="project",
        target_id=project.id,
        details={"proposal_id": proposal_id, "decision_id": saved["id"]},
    )
    db.commit()
    return saved


def discard_proposal(
    db: Session, settings: Settings, project: Project, proposal_id: int, *, actor: User, ctx: RequestContext
) -> None:
    """Descarta una propuesta del revisor (no se aplica nada) y lo audita.

    Raises:
        ProposalNotFoundError, DestinationReadOnlyError.
    """
    from app.db.models import utcnow
    from app.domain.context.errors import DestinationReadOnlyError

    del settings
    if project.destination_location.access != "rw":
        raise DestinationReadOnlyError("La ubicación de destino es de solo lectura.")
    proposal = _pending(db, project, proposal_id)
    proposal.status = "discarded"
    proposal.decided_by = actor.id
    proposal.decided_at = utcnow()
    audit.record(
        db,
        action=AuditAction.PROJECT_PROPOSAL_DISCARD,
        ctx=ctx,
        actor_id=actor.id,
        target_type="project",
        target_id=project.id,
        details={"proposal_id": proposal_id},
    )
    db.commit()
