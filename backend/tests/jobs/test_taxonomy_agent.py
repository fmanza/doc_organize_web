"""Diseñar y comprobar la taxonomía (W7, doc_organize 2.0.0rc1 M8): el diseñador (tarea ``agent``) con un guion de
herramientas en el LiteLLM falso, sin guardar nada, y la comprobación por reglas sin IA. Plantilla y documentos
sintéticos."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import AuditEntry, Project, RunEvent
from app.integrations.doc_organize import ai as library_ai
from app.jobs.context import JobFailed
from app.jobs.operations import agents as operation
from tests.conftest import ADMIN_PASSWORD, login_as
from tests.fake_litellm import FakeLiteLLM, tool_call
from tests.jobs.test_context_axes import AXES_TEMPLATE

KEY = "sk-agent-test-9o0p"


@pytest.fixture(autouse=True)
def _ai_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for family in library_ai.FAMILIES:
        for field in family.fields:
            if field.env_var:
                monkeypatch.delenv(field.env_var, raising=False)
    monkeypatch.setenv("DOC_ORGANIZE_LITELLM_BASE_URL", "https://litellm.example.internal")
    monkeypatch.setenv("DOC_ORGANIZE_LITELLM_VIRTUAL_KEY", KEY)
    monkeypatch.setenv("DOC_ORGANIZE_LITELLM_MODEL_AGENT", "agente-sintetico")


@pytest.fixture
def template(user_client: TestClient, admin: Any) -> None:
    admin_client = login_as(user_client, admin.username, ADMIN_PASSWORD)
    assert admin_client.put("/api/v1/taxonomy-templates/ejes", json={"markdown": AXES_TEMPLATE}).status_code == 201


def test_the_designer_proposes_without_saving(
    run: Any, project: Project, db: Session, migrated: Settings, monkeypatch: pytest.MonkeyPatch, template: None
) -> None:
    monkeypatch.setattr("app.jobs.context.PROGRESS_MIN_INTERVAL", 0.0)
    proxy = FakeLiteLLM(keys={KEY}).install(monkeypatch)
    change = {"axis": "domains", "action": "add", "slug": "cocina", "name": "Cocina", "keywords": ["harina", "huevos"]}
    proxy.tool_calls = [
        [tool_call("overview", {})],
        [tool_call("edit_draft", {"changes": [change]})],
        [tool_call("finish", {"rationale": "Añado «Cocina» para la receta sintética."})],
    ]
    ctx, params = run(
        {
            "operation": "taxonomy_agent",
            "catalog": "template",
            "template_name": "ejes",
            "instructions": "Cubre la receta",
            "max_steps": 10,
        }
    )
    manifest_file = migrated.locations_root / "salidas" / "Proyecto A" / "taxonomy_manifest.md"

    result = operation.run_design(ctx, params, project)

    assert result["stop_reason"] == "finished" and result["finished"] is True
    assert result["improves"] is True and result["edits"] == 1
    assert "cocina" in result["markdown"] and result["markdown"].startswith("---")
    assert result["rationale"] == "Añado «Cocina» para la receta sintética."

    def coverage(report: dict[str, Any]) -> float:
        return float(next(a["coverage"] for a in report["axes"] if a["axis"] == "domains"))

    assert coverage(result["report"]) > coverage(result["base_report"])
    assert {r.body["model"] for r in proxy.sent("agent")} == {"agente-sintetico"}
    assert not manifest_file.exists()  # nunca se guarda solo
    steps = [
        e.data
        for e in db.scalars(select(RunEvent).where(RunEvent.run_id == ctx.run_id, RunEvent.type == "progress"))
        if e.data.get("phase") == "agent_run"
    ]
    assert any(d.get("processed") == 3 and d.get("total") == 10 for d in steps), steps  # progreso por paso (rc2)
    entry = db.scalars(select(AuditEntry).where(AuditEntry.action == "project.taxonomy_agent")).one()
    assert entry.details["stop_reason"] == "finished"  # type: ignore[index]


def test_the_designer_stops_at_the_step_limit(
    run: Any, project: Project, monkeypatch: pytest.MonkeyPatch, template: None
) -> None:
    proxy = FakeLiteLLM(keys={KEY}).install(monkeypatch)
    proxy.tool_calls = [[tool_call("overview", {}, i)] for i in range(5)]
    ctx, params = run({"operation": "taxonomy_agent", "catalog": "template", "template_name": "ejes", "max_steps": 2})

    result = operation.run_design(ctx, params, project)

    assert result["stop_reason"] == "max_steps" and result["markdown"] is None and result["steps"] == 2


def test_rules_check_without_ai(run: Any, project: Project, monkeypatch: pytest.MonkeyPatch) -> None:
    proxy = FakeLiteLLM(keys={KEY}).install(monkeypatch)
    ctx, params = run({"operation": "taxonomy_check", "markdown": AXES_TEMPLATE})

    result = operation.run_check(ctx, params, project)

    report = result["report"]
    assert report["documents"] == 4 and {a["axis"] for a in report["axes"]} == {
        "domains",
        "material_types",
        "impuestos",
    }
    domains = next(a for a in report["axes"] if a["axis"] == "domains")
    assert 0 <= domains["coverage"] <= 1 and "| " in report["markdown"]
    assert proxy.requests == []  # sin IA


def test_enqueue_checks(project: Project, user_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    runs = f"/api/v1/projects/{project.id}/runs"
    no_manifest = user_client.post(runs, json={"operation": "taxonomy_agent"})
    invalid = user_client.post(runs, json={"operation": "taxonomy_check", "markdown": "no"})
    monkeypatch.delenv("DOC_ORGANIZE_LITELLM_VIRTUAL_KEY")
    no_ai = user_client.post(runs, json={"operation": "taxonomy_agent", "catalog": "none"})

    assert no_manifest.status_code == 422 and no_manifest.json()["code"] == "context_build_invalid"
    assert invalid.status_code == 422 and invalid.json()["code"] == "template_invalid"
    assert no_ai.status_code == 422 and no_ai.json()["code"] == "ai_not_configured"


def test_without_documents_it_fails_cleanly(
    run: Any, project: Project, migrated: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    import shutil

    from app.domain.scan.state import CONVERSION_DIR

    FakeLiteLLM(keys={KEY}).install(monkeypatch)
    shutil.rmtree(migrated.locations_root / "salidas" / "Proyecto A" / CONVERSION_DIR)
    ctx, params = run({"operation": "taxonomy_agent", "catalog": "none"})

    with pytest.raises(JobFailed) as failure:
        operation.run_design(ctx, params, project)
    assert failure.value.code == "no_converted_documents"
