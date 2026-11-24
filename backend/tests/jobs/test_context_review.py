"""Revisar la clasificación (W5, doc_organize 2.0 F6): la construcción deja la cola de revisión en la BD; las
decisiones (editor, destino ``rw``, auditadas, validadas contra el catálogo) se guardan donde las lee doc_organize y se
aplican al reconstruir; revocar; desfasadas cuando cambia el original. Documentos y plantilla sintéticos."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from doc_organize import CacheEntry, ConversionStatus, DocumentStatus
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import AuditEntry, ContextDocument, ContextDocumentAxisValue, Project, ProjectContext, User
from app.domain.projects.service import state_dir
from app.domain.scan.state import folder_cache
from app.jobs.operations import context as operation
from tests.api.test_documents import write_cache
from tests.conftest import ADMIN_PASSWORD, login_as
from tests.jobs.test_context_axes import AXES_TEMPLATE
from tests.jobs.test_context_operation import _finish

TEMPLATE_RUN = {"operation": "context_build", "catalog": "template", "template_name": "ejes", "build_site": False}
RECETA = "2025/receta.txt"


def _build(run: Any, project: Project, db: Session) -> Any:
    ctx, params = run(TEMPLATE_RUN)
    operation.run_build(ctx, params, project)
    _finish(db, ctx)
    return ctx


def _setup(user_client: TestClient, admin: User) -> None:
    admin_client = login_as(user_client, admin.username, ADMIN_PASSWORD)
    assert admin_client.put("/api/v1/taxonomy-templates/ejes", json={"markdown": AXES_TEMPLATE}).status_code == 201


def test_review_queue_and_a_decision_applied_on_rebuild(
    run: Any, project: Project, db: Session, user_client: TestClient, admin: User, migrated: Settings
) -> None:
    _setup(user_client, admin)
    _build(run, project, db)
    base = f"/api/v1/projects/{project.id}/context"

    page = user_client.get(f"{base}/review").json()
    unclassified = [i for i in page["items"] if i["reason"] == "unclassified"]
    assert page["counts"]["unclassified"] == len(unclassified) >= 1
    receta = next(i for i in unclassified if i["document_key"] == RECETA)
    assert receta["document"]["path"] == "receta.txt" and receta["decision"] is None
    assert str(migrated.locations_root) not in str(page)

    decided = user_client.post(
        f"{base}/decisions",
        json={"document_key": RECETA, "action": "set_axis", "axes": {"domains": ["informes"]}, "reason": "Prueba"},
    )

    assert decided.status_code == 201, decided.text
    decision = decided.json()
    assert decision["author"] == "ana"  # el usuario de la web
    assert (migrated.locations_root / "salidas" / "Proyecto A" / ".doc_organize" / "decisions.json").is_file()
    again = user_client.get(f"{base}/review", params={"reason": "unclassified"}).json()
    assert next(i for i in again["items"] if i["document_key"] == RECETA)["decision"]["id"] == decision["id"]
    entry = db.scalars(select(AuditEntry).where(AuditEntry.action == "project.decision_add")).one()
    assert entry.details["action"] == "set_axis" and entry.details["axes"] == {"domains": ["informes"]}  # type: ignore[index]

    _build(run, project, db)

    doc = db.scalars(
        select(ContextDocument).where(ContextDocument.project_id == project.id, ContextDocument.document_key == RECETA)
    ).one()
    assert doc.domain_slug == "informes"
    value = db.scalars(
        select(ContextDocumentAxisValue).where(
            ContextDocumentAxisValue.project_id == project.id,
            ContextDocumentAxisValue.seq == doc.seq,
            ContextDocumentAxisValue.axis == "domains",
        )
    ).one()
    assert value.classified_by == "human"
    stored = db.get(ProjectContext, project.id)
    assert stored is not None and stored.decisions_applied == 1

    revoked = user_client.post(f"{base}/decisions/{decision['id']}/revoke", json={"reason": "Ya no"})
    assert revoked.status_code == 204
    listing = user_client.get(f"{base}/decisions").json()
    assert listing["decisions"] == [] and listing["revoked"][0]["revoke_reason"] == "Ya no"
    assert user_client.post(f"{base}/decisions/{decision['id']}/revoke", json={}).status_code == 404


def test_decisions_are_validated_against_the_catalog(
    run: Any, project: Project, db: Session, user_client: TestClient, admin: User, make_user: Callable[..., User]
) -> None:
    _setup(user_client, admin)
    _build(run, project, db)
    url = f"/api/v1/projects/{project.id}/context/decisions"

    def code(body: dict[str, Any]) -> tuple[int, str | None]:
        response = user_client.post(url, json=body)
        return response.status_code, response.json().get("code")

    assert code({"document_key": RECETA, "action": "set_axis", "axes": {"domains": ["inventado"]}}) == (
        422,
        "decision_invalid",
    )
    assert code({"document_key": RECETA, "action": "set_axis", "axes": {"domains": ["facturas", "informes"]}})[0] == 422
    assert code({"document_key": RECETA, "action": "set_axis", "axes": {"otro_eje": ["x"]}})[0] == 422
    assert code({"document_key": RECETA, "action": "exclude", "axes": {"domains": ["informes"]}})[0] == 422
    assert code({"document_key": RECETA, "action": "set_current_version"})[0] == 422  # sin grupo de versiones
    assert code({"document_key": "no/existe.txt", "action": "exclude"}) == (404, "decision_document_not_found")
    multi = code({"document_key": RECETA, "action": "set_axis", "axes": {"impuestos": ["iva", "irpf"]}})
    assert multi[0] == 201  # eje de varios valores
    viewer = make_user("lectora")
    user_client.post(f"/api/v1/projects/{project.id}/members", json={"user_id": viewer.id, "role": "viewer"})
    assert (
        login_as(user_client, "lectora").post(url, json={"document_key": RECETA, "action": "exclude"}).status_code
        == 403
    )


def test_a_decision_goes_stale_when_the_original_changes(
    run: Any, project: Project, db: Session, user_client: TestClient, admin: User, migrated: Settings
) -> None:
    _setup(user_client, admin)
    _build(run, project, db)
    base = f"/api/v1/projects/{project.id}/context"
    user_client.post(f"{base}/decisions", json={"document_key": RECETA, "action": "exclude"})
    source = (migrated.locations_root / "origen").resolve()
    write_cache(
        folder_cache(state_dir(migrated, project.id), "2025"),
        [
            CacheEntry(
                file_path=str(source / "2025" / "receta.txt"),
                sha256_hash="9" * 64,
                timestamp=time.time(),
                status=DocumentStatus.MODIFIED,
                conversion_status=ConversionStatus.SUCCESS,
            )
        ],
    )

    _build(run, project, db)

    listing = user_client.get(f"{base}/decisions").json()
    assert [(i["document_key"], i["reason"]) for i in listing["stale"]] == [(RECETA, "source_changed")]
    review = user_client.get(f"{base}/review", params={"reason": "stale_decision"}).json()
    assert review["total"] == 1 and review["items"][0]["document_key"] == RECETA
