"""Consumo de IA por ejecución (web 2.1, IA › Uso): qué se registra de cada operación, sin duplicar, sin tumbar el run
y los agregados por día en la hora local. LiteLLM falso y documentos sintéticos."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.db.models import AiUsageRecord, Project, Run
from app.db.session import get_engine
from app.domain.ai import usage_log
from app.jobs import runner
from app.jobs.operations import ai as draft_operation
from app.jobs.operations import context as operation
from tests.conftest import ADMIN_PASSWORD, login_as
from tests.fake_litellm import FakeLiteLLM, classify_answer
from tests.jobs.test_ai_operation import AI_DOMAINS, DRAFT, KEY, _ai_env  # noqa: F401 - fixture autouse


@pytest.fixture
def fake_litellm(monkeypatch: pytest.MonkeyPatch) -> FakeLiteLLM:
    """LiteLLM falso con la clave general (la del entorno de ``_ai_env``)."""
    return FakeLiteLLM(keys={KEY}).install(monkeypatch)


def _rows(db: Session, run_id: str) -> list[AiUsageRecord]:
    db.expire_all()
    return list(db.scalars(select(AiUsageRecord).where(AiUsageRecord.run_id == run_id)))


def test_context_build_records_one_row_per_task_without_duplicates(
    run: Any, project: Project, db: Session, fake_litellm: FakeLiteLLM
) -> None:
    fake_litellm.answers["classify"] = classify_answer({"domains": ["informes"]}, confidence=0.8)
    ctx, params = run(AI_DOMAINS)
    result = operation.run_build(ctx, params, project)
    stored = db.get(Run, ctx.run_id)
    assert stored is not None

    assert usage_log.record(db, stored, project, result) == 1
    db.commit()
    assert usage_log.record(db, stored, project, result) == 1  # un reintento actualiza, no duplica (A11)
    db.commit()

    [row] = _rows(db, ctx.run_id)
    assert (row.task, row.operation, row.project_id, row.project_name) == (
        "classify",
        "context_build",
        project.id,
        project.name,
    )
    assert row.model and row.calls == result["ai"]["calls"] >= 1 and row.prompt_tokens > 0
    assert row.tenant_id == project.tenant_id and row.tokens_estimated is False


def test_taxonomy_draft_records_its_tokens_and_model(
    run: Any, project: Project, db: Session, fake_litellm: FakeLiteLLM
) -> None:
    fake_litellm.answers["taxonomy_design"] = lambda _: DRAFT
    ctx, params = run({"operation": "taxonomy_draft", "sample_size": 3})

    result = draft_operation.run(ctx, params, project)

    [row] = usage_log.rows_from_result("taxonomy_draft", result)
    assert row.task == "taxonomy_design" and row.calls == 1 and row.model == result["model"]
    assert row.prompt_tokens == result["prompt_tokens"] > 0
    assert KEY not in str(result)


def test_rows_from_result_reads_agents_semantic_and_dry_runs() -> None:
    agent = usage_log.rows_from_result(
        "taxonomy_agent",
        {"steps": 4, "prompt_tokens": 900, "completion_tokens": 120, "tokens_estimated": True, "model": "agente"},
    )
    assert [(r.task, r.calls, r.tokens_estimated, r.model) for r in agent] == [("agent", 4, True, "agente")]
    build = usage_log.rows_from_result(
        "context_build",
        {
            "ai": {"enabled": False},
            "ai_enrichment": {"enabled": True, "calls": 3, "cached": 2, "prompt_tokens": 50, "model": "describe"},
            "semantic": {"enabled": True, "embedded": 7, "cached": 1, "prompt_tokens": 70},
        },
    )
    assert [(r.task, r.calls, r.cached) for r in build] == [("enrich", 3, 2), ("embed", 7, 1)]
    dry = usage_log.rows_from_result("context_dry_run", {"ai": {"scope": "off", "calls": 0}})
    assert dry == []
    # Sin nada gastado no hay fila; operaciones sin IA, tampoco.
    assert usage_log.rows_from_result("taxonomy_agent", {"steps": 0}) == []
    assert usage_log.rows_from_result("scan", {"ai": {"enabled": True, "calls": 9}}) == []


def test_a_failure_recording_usage_never_breaks_the_run(
    run: Any, project: Project, db: Session, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    ctx, _ = run({"operation": "noop"})
    stored = db.get(Run, ctx.run_id)
    assert stored is not None

    def _boom(*_: Any) -> int:
        raise RuntimeError("base de datos caída")

    monkeypatch.setattr(usage_log, "record", _boom)
    factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    with caplog.at_level("WARNING"):
        runner._record_ai_usage(factory, stored, project, {"ai": {"enabled": True, "calls": 1}})
    assert "No se pudo registrar el consumo de IA" in caplog.text


def _record(db: Session, project: Project, run_id: str, task: str, created_at: datetime, tokens: int) -> None:
    db.add(Run(id=run_id, project_id=project.id, operation="context_build", params={}, status="succeeded"))
    db.flush()
    db.add(
        AiUsageRecord(
            run_id=run_id,
            project_id=project.id,
            project_name=project.name,
            tenant_id=project.tenant_id,
            operation="context_build",
            task=task,
            model="modelo",
            calls=2,
            cached=1,
            prompt_tokens=tokens,
            completion_tokens=10,
            created_at=created_at,
        )
    )
    db.commit()


def test_summary_groups_by_local_day_and_period(project: Project, db: Session) -> None:
    now = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)
    # 23:30 UTC del 20 es ya el 21 en Madrid (UTC+1 en noviembre).
    _record(
        db, project, "00000000-0000-4000-8000-000000000001", "classify", datetime(2026, 11, 20, 23, 30, tzinfo=UTC), 100
    )
    _record(
        db, project, "00000000-0000-4000-8000-000000000002", "enrich", datetime(2026, 11, 22, 9, 0, tzinfo=UTC), 300
    )
    _record(
        db, project, "00000000-0000-4000-8000-000000000003", "classify", datetime(2026, 10, 1, 9, 0, tzinfo=UTC), 900
    )

    madrid = usage_log.summary(db, period="7d", tz_name="Europe/Madrid", now=now)
    assert madrid.timezone == "Europe/Madrid"
    # Los 7 días del periodo, con ceros en los que no hubo consumo (el gráfico no junta días separados).
    assert list(madrid.by_day)[0] == date(2026, 11, 16) and list(madrid.by_day)[-1] == date(2026, 11, 22)
    assert len(madrid.by_day) == 7 and madrid.by_day[date(2026, 11, 18)].prompt_tokens == 0
    assert madrid.by_day[date(2026, 11, 21)].prompt_tokens == 100
    assert madrid.totals.runs == 2 and madrid.totals.prompt_tokens == 400 and madrid.totals.cached == 2
    assert set(madrid.by_task) == {"classify", "enrich"}
    assert [run.run_id for run in madrid.top_runs][0] == "00000000-0000-4000-8000-000000000002"

    utc = usage_log.summary(db, period="7d", tz_name="no/existe", now=now)  # zona no válida: UTC
    assert utc.timezone == "UTC" and utc.by_day[date(2026, 11, 20)].prompt_tokens == 100
    assert usage_log.summary(db, period="all", tz_name=None, now=now).totals.runs == 3
    assert usage_log.summary(db, period="month", tz_name="Europe/Madrid", now=now).totals.runs == 2


def test_usage_api_and_run_detail(
    user_client: TestClient, project: Project, db: Session, admin: Any, migrated: Settings
) -> None:
    now = datetime.now(UTC)
    run_id = "00000000-0000-4000-8000-000000000009"
    _record(db, project, run_id, "classify", now, 120)

    detail = user_client.get(f"/api/v1/runs/{run_id}").json()  # miembro del proyecto: ve los tokens
    assert detail["ai_usage"] == [
        {
            "task": "classify",
            "model": "modelo",
            "calls": 2,
            "cached": 1,
            "failed": 0,
            "prompt_tokens": 120,
            "completion_tokens": 10,
            "tokens_estimated": False,
        }
    ]
    assert user_client.get("/api/v1/admin/ai-usage").status_code == 403

    admin_client = login_as(user_client, admin.username, ADMIN_PASSWORD)
    body = admin_client.get("/api/v1/admin/ai-usage?period=7d&tz=Europe/Madrid").json()
    local = body["local"]
    assert local["period"] == "7d" and local["timezone"] == "Europe/Madrid"
    assert local["totals"]["prompt_tokens"] == 120 and local["totals"]["runs"] == 1
    assert [g["key"] for g in local["by_task"]] == ["classify"]
    assert local["by_project"][0]["label"] == project.name and local["by_project"][0]["project_id"] == project.id
    assert local["top_runs"][0]["run_id"] == run_id
    assert admin_client.get("/api/v1/admin/ai-usage?period=1y").status_code == 422
