"""Clasificación semántica (W6, doc_organize 2.0 G4): el ajuste del proyecto llega a ``build(semantic=,
semantic_threshold=)`` con la tarea ``embed`` de «Modelos de IA» (LiteLLM falso con embeddings deterministas); sin IA
configurada, se construye sin ella y se avisa. Plantilla y documentos sintéticos."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import AuditEntry, ContextDocument, ContextDocumentAxisValue, Project, RunEvent
from app.integrations.doc_organize import ai as library_ai
from app.jobs.operations import context as operation
from tests.conftest import ADMIN_PASSWORD, login_as
from tests.fake_litellm import FakeLiteLLM
from tests.jobs.test_context_axes import AXES_TEMPLATE
from tests.jobs.test_context_operation import _finish

KEY = "sk-semantic-test-7u8i"
TEMPLATE_RUN = {"operation": "context_build", "catalog": "template", "template_name": "ejes", "build_site": False}


@pytest.fixture(autouse=True)
def _ai_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for family in library_ai.FAMILIES:
        for field in family.fields:
            if field.env_var:
                monkeypatch.delenv(field.env_var, raising=False)


@pytest.fixture
def semantic(project: Project, db: Session, user_client: TestClient, admin: Any) -> Project:
    admin_client = login_as(user_client, admin.username, ADMIN_PASSWORD)
    assert admin_client.put("/api/v1/taxonomy-templates/ejes", json={"markdown": AXES_TEMPLATE}).status_code == 201
    response = user_client.put(
        f"/api/v1/projects/{project.id}/ai-settings", json={"context_semantic": True, "context_semantic_threshold": 0.5}
    )
    assert response.status_code == 200, response.text
    assert response.json()["context_semantic"] is True and response.json()["context_semantic_threshold"] == 0.5
    project.context_semantic = True
    project.context_semantic_threshold = 0.5
    return project


def test_semantic_fills_empty_axes_with_embeddings(
    run: Any, semantic: Project, db: Session, monkeypatch: pytest.MonkeyPatch, user_client: TestClient
) -> None:
    monkeypatch.setenv("DOC_ORGANIZE_LITELLM_BASE_URL", "https://litellm.example.internal")
    monkeypatch.setenv("DOC_ORGANIZE_LITELLM_VIRTUAL_KEY", KEY)
    monkeypatch.setenv("DOC_ORGANIZE_LITELLM_MODEL_EMBED", "embebedor-sintetico")
    proxy = FakeLiteLLM(keys={KEY}).install(monkeypatch)
    ctx, params = run(TEMPLATE_RUN)

    result = operation.run_build(ctx, params, semantic).stored()

    embeddings = proxy.sent(path="/embeddings")
    assert embeddings and {r.body["model"] for r in embeddings} == {"embebedor-sintetico"}
    assert proxy.sent("classify") == []  # sin alcance de IA: solo embeddings
    assert result["semantic"]["enabled"] is True and result["semantic"]["embedded"] > 0
    assert result["semantic"]["index_vectors"] >= result["semantic"]["embedded"] > 0  # rc2: embedding_index_info
    assert result["semantic"]["index_bytes"] > 0
    values = db.scalars(
        select(ContextDocumentAxisValue).where(
            ContextDocumentAxisValue.project_id == semantic.id, ContextDocumentAxisValue.classified_by == "semantic"
        )
    ).all()
    assert values  # al menos un eje rellenado por semántica
    assert result["semantic"]["assigned"] >= 1
    events = " ".join(str(e.data) for e in db.scalars(select(RunEvent).where(RunEvent.run_id == ctx.run_id)))
    assert "Semántica:" in events and KEY not in events
    _finish(db, ctx)
    # Un documento cuyo dominio lo asignó la semántica se lista (W9: antes, 500 por `classified_by` = semantic).
    by_semantic = db.scalars(
        select(ContextDocument).where(
            ContextDocument.project_id == semantic.id, ContextDocument.classified_by == "semantic"
        )
    ).all()
    assert by_semantic
    for doc in by_semantic:
        listed = user_client.get(
            f"/api/v1/projects/{semantic.id}/context/documents", params={"domain": doc.domain_slug}
        )
        assert listed.status_code == 200, listed.text


def test_without_ai_configured_it_builds_without_semantic(run: Any, semantic: Project, db: Session) -> None:
    ctx, params = run(TEMPLATE_RUN)

    result = operation.run_build(ctx, params, semantic).stored()

    assert result["semantic"] == {"enabled": False}
    events = " ".join(str(e.data) for e in db.scalars(select(RunEvent).where(RunEvent.run_id == ctx.run_id)))
    assert "«Modelos de IA» no está configurado" in events


def test_threshold_is_validated_and_audited(semantic: Project, user_client: TestClient, db: Session) -> None:
    url = f"/api/v1/projects/{semantic.id}/ai-settings"
    assert user_client.put(url, json={"context_semantic_threshold": 1.5}).status_code == 422
    entry = db.scalars(select(AuditEntry).where(AuditEntry.action == "project.ai_settings_update")).one()
    assert entry.details == {"context_semantic": [False, True], "context_semantic_threshold": [0.75, 0.5]}
    db.execute(update(Project).where(Project.id == semantic.id).values(context_semantic=False))
    db.commit()
