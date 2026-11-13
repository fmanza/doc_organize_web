"""IA en los jobs (Fase 8): ``context_build`` con ``ai_classification`` y ``taxonomy_draft``. Usan el ``ContextBuilder`` y
los clientes reales de doc_organize contra un LiteLLM falso (``httpx.MockTransport``), con documentos sintéticos. Se
comprueba también que ni la clave ni las rutas del contenedor salen en el resultado, los eventos o lo enviado."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable, Iterator
from typing import Any

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import AuditEntry, ContextDocument, Project, ProjectContext, RunEvent
from app.domain.ai import settings as ai_settings
from app.domain.runs.operations import ContextBuildParams, context_ai_family
from app.domain.scan.state import CONVERSION_DIR
from app.integrations.doc_organize import ai as library_ai
from app.jobs.context import JobFailed
from app.jobs.operations import ai as draft_operation
from app.jobs.operations import context as operation
from tests.jobs.test_context_operation import DOMAINS

KEY = "sk-job-test-secret-7q6w"
BASE_URL = "https://litellm.example.internal"


@pytest.fixture(autouse=True)
def _ai_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Las tres familias de LiteLLM configuradas por el entorno (precedencia más baja que ``ai_settings``)."""
    for family in library_ai.FAMILIES:
        for field in family.fields:
            monkeypatch.delenv(field.env_var, raising=False)
    for prefix in ("CLASSIFICATION", "TAXONOMY_CLASSIFICATION", "TAXONOMY_MANIFEST_DRAFT"):
        monkeypatch.setenv(f"DOC_ORGANIZE_LITELLM_{prefix}_BASE_URL", BASE_URL)
        monkeypatch.setenv(f"DOC_ORGANIZE_LITELLM_{prefix}_VIRTUAL_KEY", KEY)


@pytest.fixture
def litellm(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[[Callable[[dict[str, Any]], httpx.Response]], list]]:
    """Sustituye el transporte HTTP de los clientes de IA; devuelve los cuerpos JSON recibidos."""

    def _install(answer: Callable[[dict[str, Any]], httpx.Response]) -> list[dict[str, Any]]:
        bodies: list[dict[str, Any]] = []

        def _handle(request: httpx.Request) -> httpx.Response:
            assert request.headers["authorization"] == f"Bearer {KEY}"
            body = json.loads(request.content)
            bodies.append(body)
            return answer(body)

        monkeypatch.setattr(library_ai, "_transport", lambda _: httpx.MockTransport(_handle))
        return bodies

    yield _install


def _chat(content: dict[str, Any]) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(content)}}]})


def _events(db: Session, run_id: str) -> str:
    return json.dumps(
        [e.data for e in db.scalars(select(RunEvent).where(RunEvent.run_id == run_id))], ensure_ascii=False
    )


AI_DOMAINS = {**DOMAINS, "ai_classification": True}


def test_family_follows_the_catalog() -> None:
    assert context_ai_family(ContextBuildParams(catalog="discover")) == "litellm_classification"
    assert context_ai_family(ContextBuildParams(catalog="manifest")) == "litellm_taxonomy_classification"


def test_build_with_ai_classifies_what_rules_leave(
    run: Any, project: Project, db: Session, migrated: Settings, litellm: Any
) -> None:
    bodies = litellm(lambda _: _chat({"domain": "informes", "confidence": 0.8}))
    ctx, params = run(AI_DOMAINS)

    result = operation.run_build(ctx, params, project)

    ai = result["ai"]
    assert ai["enabled"] is True and ai["calls"] == len(bodies) >= 1 and ai["classified"] == ai["calls"]
    assert ai["stopped"] is None and ai["failed"] == 0
    stored = db.get(ProjectContext, project.id)
    assert stored is not None and stored.ai_classification is True
    docs = {d.path: d for d in db.scalars(select(ContextDocument).where(ContextDocument.project_id == project.id))}
    assert docs["receta.txt"].domain_slug == "informes" and docs["receta.txt"].classified_by == "ai"
    assert {d.classified_by for d in docs.values()} <= {"ai", "rules"}
    sent = json.dumps(bodies)
    assert str(migrated.locations_root) not in sent and "harina" in sent
    trail = _events(db, ctx.run_id) + json.dumps(result)
    assert KEY not in trail and BASE_URL not in trail


def test_build_stops_calling_after_a_rejected_key(
    run: Any, project: Project, db: Session, migrated: Settings, litellm: Any
) -> None:
    bodies = litellm(lambda _: httpx.Response(401))
    ctx, params = run(AI_DOMAINS)

    result = operation.run_build(ctx, params, project)

    assert len(bodies) == 1 and result["ai"]["stopped"] == "auth" and result["ai"]["failed"] == 1
    assert result["documents"] + result["unclassified"] == 4  # el contexto se construye igualmente
    events = _events(db, ctx.run_id)
    assert "rechazó la clave" in events and KEY not in events and BASE_URL not in events


def test_build_respects_the_budget(
    run: Any, project: Project, db: Session, migrated: Settings, litellm: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    bodies = litellm(lambda _: _chat({"domain": None}))
    ctx, params = run(AI_DOMAINS)
    ctx.settings = migrated.model_copy(update={"ai_max_documents_per_run": 1})

    result = operation.run_build(ctx, params, project)

    if result["ai"]["calls"]:  # solo si las reglas dejaron más de uno sin clasificar se llega al tope
        assert len(bodies) == 1
    assert result["ai"]["calls"] <= 1


def test_build_stops_after_consecutive_connection_errors(
    run: Any, project: Project, migrated: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """L-3a: tras ``MAX_CONNECTION_FAILURES`` errores de conexión seguidos doc_organize deja de llamar (G33)."""
    calls: list[httpx.Request] = []

    def _down(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        raise httpx.ConnectError("caído", request=request)

    monkeypatch.setattr(library_ai, "_transport", lambda _: httpx.MockTransport(_down))
    monkeypatch.setattr(library_ai, "MAX_CONNECTION_FAILURES", 1)
    ctx, params = run(AI_DOMAINS)
    ctx.settings = migrated.model_copy(update={"ai_retries": 0})

    result = operation.run_build(ctx, params, project)

    assert len(calls) == 1 and result["ai"]["stopped"] == "connection" and result["ai"]["failed"] == 1


def test_build_without_configuration_fails_cleanly(
    run: Any, project: Project, monkeypatch: pytest.MonkeyPatch, litellm: Any
) -> None:
    litellm(lambda _: _chat({}))
    ctx, params = run(AI_DOMAINS)
    monkeypatch.delenv("DOC_ORGANIZE_LITELLM_CLASSIFICATION_VIRTUAL_KEY")  # se quitó después de encolar

    with pytest.raises(JobFailed) as failure:
        operation.run_build(ctx, params, project)

    assert failure.value.code == "ai_not_configured"


DRAFT = {
    "domains": [{"slug": "facturas", "name": "Facturas"}, {"slug": "obras", "name": "Obras"}],
    "material_types": [{"slug": "informe", "name": "Informe"}],
    "reasoning": "Muestra sintética",
}


def test_taxonomy_draft_returns_the_markdown_without_saving(
    run: Any, project: Project, db: Session, migrated: Settings, litellm: Any
) -> None:
    bodies = litellm(lambda _: _chat(DRAFT))
    ctx, params = run({"operation": "taxonomy_draft", "sample_size": 3})

    result = draft_operation.run(ctx, params, project)

    assert result["manifest_markdown"].startswith("---\ndomains:")
    assert result["sample_documents"] == 3 and result["total_documents"] == 4
    assert [d["slug"] for d in result["domains"]] == ["facturas", "obras"]
    assert not (migrated.locations_root / "salidas" / "Proyecto A" / "taxonomy_manifest.md").exists()
    prompt = bodies[0]["messages"][1]["content"]  # el de sistema es de doc_organize (habla de «material de origen»)
    assert "Carpeta: 2024/obras" in prompt
    for container in (str(migrated.locations_root), migrated.locations_root.as_posix(), "salidas", "origen", "mnt"):
        assert container not in prompt
    audit = db.scalars(select(AuditEntry).where(AuditEntry.action == "project.taxonomy_draft")).one()
    assert audit.details["sample_documents"] == 3  # type: ignore[index]
    assert KEY not in _events(db, ctx.run_id) + json.dumps(result)


@pytest.mark.parametrize(
    ("answer", "code"),
    [
        (lambda _: httpx.Response(403), "ai_auth"),
        (lambda _: httpx.Response(500), "ai_error"),
        (lambda _: _chat({"domains": []}), "ai_error"),
        (lambda _: _chat({**DRAFT, "reasoning": "x" * 300_000}), "ai_error"),  # mayor que un manifiesto
    ],
)
def test_taxonomy_draft_errors_carry_no_details(
    run: Any, project: Project, litellm: Any, answer: Callable[[dict[str, Any]], httpx.Response], code: str
) -> None:
    litellm(answer)
    ctx, params = run({"operation": "taxonomy_draft"})

    with pytest.raises(JobFailed) as failure:
        draft_operation.run(ctx, params, project)

    assert failure.value.code == code and BASE_URL not in failure.value.message


def test_draft_has_its_own_timeout_and_no_retries(db: Session, migrated: Settings) -> None:
    """Hotfix 1.4.5: el borrador es una petición larga; las demás familias siguen con el plazo general."""
    draft = ai_settings.connection(db, migrated, "litellm_taxonomy_manifest_draft")
    classification = ai_settings.connection(db, migrated, "litellm_classification")

    assert (draft.timeout_s, draft.retries) == (300.0, 0)
    assert (classification.timeout_s, classification.retries) == (30.0, 2)


@pytest.mark.parametrize(
    ("error", "code", "timed_out"),
    [(httpx.ReadTimeout, "ai_timeout", True), (httpx.ConnectError, "ai_connection", False)],
)
def test_taxonomy_draft_tells_a_timeout_from_a_connection_error(
    run: Any,
    project: Project,
    litellm: Any,
    caplog: pytest.LogCaptureFixture,
    error: type[httpx.TransportError],
    code: str,
    timed_out: bool,
) -> None:
    """Hotfix 1.4.5: un modelo lento no es «no se pudo conectar», no se reintenta y la causa queda en el log."""

    def _fail(_: dict[str, Any]) -> httpx.Response:
        raise error("sin respuesta")

    bodies = litellm(_fail)
    ctx, params = run({"operation": "taxonomy_draft"})

    with caplog.at_level("WARNING", logger=library_ai.__name__), pytest.raises(JobFailed) as failure:
        draft_operation.run(ctx, params, project)

    assert failure.value.code == code and len(bodies) == 1  # ai_draft_retries = 0 por defecto
    assert ("300 s" in failure.value.message) is timed_out and BASE_URL not in failure.value.message
    (record,) = [r for r in caplog.records if r.name == library_ai.__name__]
    assert record.cause == error.__name__ and record.timed_out is timed_out  # type: ignore[attr-defined]
    logged = record.getMessage() + json.dumps({k: str(v) for k, v in vars(record).items()})
    assert KEY not in logged and BASE_URL not in logged


def test_taxonomy_draft_needs_converted_documents(run: Any, project: Project, migrated: Settings, litellm: Any) -> None:
    bodies = litellm(lambda _: _chat(DRAFT))
    shutil.rmtree(migrated.locations_root / "salidas" / "Proyecto A" / CONVERSION_DIR)
    ctx, params = run({"operation": "taxonomy_draft"})

    with pytest.raises(JobFailed) as failure:
        draft_operation.run(ctx, params, project)

    assert failure.value.code == "no_converted_documents" and bodies == []
