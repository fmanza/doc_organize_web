"""Propuestas del revisor e informe del auditor (W7, doc_organize 2.0.0rc1 M9): el revisor (tarea ``agent``) propone con
un guion de herramientas en el LiteLLM falso; las propuestas se guardan en la BD sin aplicarse (D14) y una persona las
acepta (→ decisión suya) o las descarta. El auditor no usa IA. Plantilla y documentos sintéticos."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import AuditEntry, ContextReviewProposal, Project, User
from app.jobs.operations import agents as operation
from tests.conftest import login_as
from tests.fake_litellm import FakeLiteLLM, tool_call
from tests.jobs.test_context_review import RECETA, _build, _setup
from tests.jobs.test_taxonomy_agent import KEY, _ai_env  # noqa: F401  (fixture autouse)

PROPOSAL = {
    "document_key": RECETA,
    "action": "set_axis",
    "axes": {"domains": ["informes"]},
    "rationale": "Habla de un informe sintético.",
    "evidence": "informe",
}


def _review(run: Any, project: Project, monkeypatch: pytest.MonkeyPatch, *proposals: dict[str, Any]) -> dict[str, Any]:
    proxy = FakeLiteLLM(keys={KEY}).install(monkeypatch)
    proxy.tool_calls = [
        [tool_call("list_queue", {})],
        *[[tool_call("propose_decision", p, i)] for i, p in enumerate(proposals)],
        [tool_call("finish", {"summary": "Propongo lo que veo claro."})],
    ]
    ctx, params = run({"operation": "context_review_agent", "max_items": 5, "max_steps": 10})
    return operation.run_review(ctx, params, project)


def test_the_reviewer_stores_proposals_without_applying_them(
    run: Any, project: Project, db: Session, user_client: TestClient, admin: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(user_client, admin)
    _build(run, project, db)
    base = f"/api/v1/projects/{project.id}/context"

    result = _review(run, project, monkeypatch, PROPOSAL)

    assert result["stop_reason"] == "finished" and result["proposals"] == 1
    assert result["summary"] == "Propongo lo que veo claro."
    page = user_client.get(f"{base}/review/proposals").json()
    (proposal,) = page["items"]
    assert proposal["document_key"] == RECETA and proposal["axes"] == {"domains": ["informes"]}
    assert proposal["document"]["path"] == "receta.txt"
    assert user_client.get(f"{base}/review").json()["counts"]["reviewer_proposal"] == 1
    assert user_client.get(f"{base}/decisions").json()["decisions"] == []  # no se aplica sola (D14)
    assert db.scalars(select(AuditEntry).where(AuditEntry.action == "project.review_agent")).one()

    # otra pasada sustituye las pendientes, no las acumula
    _review(run, project, monkeypatch, PROPOSAL)
    assert len(user_client.get(f"{base}/review/proposals").json()["items"]) == 1


def test_accepting_saves_a_decision_of_the_user_and_discarding_does_not(
    run: Any,
    project: Project,
    db: Session,
    user_client: TestClient,
    admin: User,
    monkeypatch: pytest.MonkeyPatch,
    make_user: Callable[..., User],
) -> None:
    _setup(user_client, admin)
    _build(run, project, db)
    base = f"/api/v1/projects/{project.id}/context"
    exclude = {"document_key": RECETA, "action": "exclude", "rationale": "Sobra."}
    _review(run, project, monkeypatch, PROPOSAL)
    (first,) = user_client.get(f"{base}/review/proposals").json()["items"]

    viewer = make_user("lectora")
    user_client.post(f"/api/v1/projects/{project.id}/members", json={"user_id": viewer.id, "role": "viewer"})
    denied = login_as(user_client, "lectora").post(f"{base}/review/proposals/{first['id']}/accept")
    assert denied.status_code == 403

    accepted = user_client.post(f"{base}/review/proposals/{first['id']}/accept")

    assert accepted.status_code == 200, accepted.text
    decision = accepted.json()
    assert decision["author"] == "ana" and decision["axes"] == {"domains": ["informes"]}
    assert "Propuesta del revisor" in decision["reason"]
    stored = db.get(ContextReviewProposal, first["id"])
    assert stored is not None and stored.status == "accepted" and stored.decision_id == decision["id"]
    assert user_client.post(f"{base}/review/proposals/{first['id']}/accept").status_code == 404  # ya no está pendiente
    assert db.scalars(select(AuditEntry).where(AuditEntry.action == "project.proposal_accept")).one()

    _review(run, project, monkeypatch, exclude)
    (second,) = user_client.get(f"{base}/review/proposals").json()["items"]
    assert user_client.post(f"{base}/review/proposals/{second['id']}/discard").status_code == 204
    assert user_client.get(f"{base}/review/proposals").json()["items"] == []
    assert len(user_client.get(f"{base}/decisions").json()["decisions"]) == 1  # solo la aceptada
    assert db.scalars(select(AuditEntry).where(AuditEntry.action == "project.proposal_discard")).one()


def test_review_agent_requires_a_context_and_ai(
    run: Any, project: Project, db: Session, user_client: TestClient, admin: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    runs = f"/api/v1/projects/{project.id}/runs"
    no_context = user_client.post(runs, json={"operation": "context_review_agent"})
    _setup(user_client, admin)
    _build(run, project, db)
    monkeypatch.delenv("DOC_ORGANIZE_LITELLM_VIRTUAL_KEY")
    no_ai = user_client.post(runs, json={"operation": "context_review_agent"})

    assert no_context.status_code == 404 and no_context.json()["code"] == "context_not_found"
    assert no_ai.status_code == 422 and no_ai.json()["code"] == "ai_not_configured"


def test_the_auditor_reports_without_ai(
    run: Any,
    project: Project,
    db: Session,
    user_client: TestClient,
    admin: User,
    monkeypatch: pytest.MonkeyPatch,
    migrated: Settings,
) -> None:
    _setup(user_client, admin)
    _build(run, project, db)
    proxy = FakeLiteLLM(keys={KEY}).install(monkeypatch)
    ctx, params = run({"operation": "context_audit"})

    result = operation.run_audit(ctx, params, project)

    report = result["audit"]
    assert report["documents"] >= 1 and {a["axis"] for a in report["axes"]} >= {"domains", "impuestos"}
    assert "markdown" in report and isinstance(report["findings"], list)
    assert proxy.requests == []
    assert str(migrated.locations_root) not in str(report)
