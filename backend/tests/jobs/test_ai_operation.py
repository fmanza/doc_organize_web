"""IA en los jobs con doc_organize 2.0 (W2): ``context_build`` con ``ai_classification``/``ai_enrichment`` y
``taxonomy_draft``. Usan el ``ContextBuilder`` y el cliente único (``LlmClient``) reales de doc_organize contra un
LiteLLM falso que exige ``json_schema`` estricto (``tests/fake_litellm.py``), con documentos sintéticos. Se comprueba
también que ni la clave ni las rutas del contenedor salen en el resultado, los eventos o lo enviado."""

from __future__ import annotations

import json
import shutil
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import AiSetting, AuditEntry, ContextDocument, Project, ProjectContext, RunEvent
from app.domain.ai import settings as ai_settings
from app.domain.runs.operations import ContextBuildParams, context_ai_tasks
from app.domain.scan.state import CONVERSION_DIR
from app.integrations.doc_organize import ai as library_ai
from app.jobs.context import JobFailed
from app.jobs.operations import ai as draft_operation
from app.jobs.operations import context as operation
from tests.conftest import ADMIN_PASSWORD, login_as
from tests.fake_litellm import FakeLiteLLM, chat_response, classify_answer
from tests.jobs.test_context_axes import AXES_TEMPLATE
from tests.jobs.test_context_operation import DOMAINS, _finish

KEY = "sk-job-test-secret-7q6w"
ENRICH_KEY = "sk-job-enrich-secret-2k9d"
BASE_URL = "https://litellm.example.internal"


@pytest.fixture(autouse=True)
def _ai_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """La familia ``litellm`` configurada por el entorno (variables de 2.0, precedencia más baja que ``ai_settings``)."""
    for family in library_ai.FAMILIES:
        for field in family.fields:
            if field.env_var:
                monkeypatch.delenv(field.env_var, raising=False)
    monkeypatch.setenv("DOC_ORGANIZE_LITELLM_BASE_URL", BASE_URL)
    monkeypatch.setenv("DOC_ORGANIZE_LITELLM_VIRTUAL_KEY", KEY)


@pytest.fixture
def litellm(monkeypatch: pytest.MonkeyPatch) -> FakeLiteLLM:
    """LiteLLM falso que acepta la clave general (y la propia de ``enrich``) y exige ``json_schema`` estricto."""
    return FakeLiteLLM(keys={KEY, ENRICH_KEY}).install(monkeypatch)


def _events(db: Session, run_id: str) -> str:
    return json.dumps(
        [e.data for e in db.scalars(select(RunEvent).where(RunEvent.run_id == run_id))], ensure_ascii=False
    )


AI_DOMAINS = {**DOMAINS, "ai_classification": True}


def test_tasks_follow_the_options() -> None:
    assert context_ai_tasks(ContextBuildParams(catalog="discover")) == []
    assert context_ai_tasks(ContextBuildParams(catalog="manifest", ai_classification=True)) == ["classify"]
    assert context_ai_tasks(ContextBuildParams(ai_classification=True, ai_enrichment=True)) == ["classify", "enrich"]


def test_build_with_ai_classifies_what_rules_leave(
    run: Any, project: Project, db: Session, migrated: Settings, litellm: FakeLiteLLM
) -> None:
    litellm.answers["classify"] = classify_answer({"domains": ["informes"]}, confidence=0.8)
    ctx, params = run(AI_DOMAINS)

    result = operation.run_build(ctx, params, project)

    ai = result["ai"]
    sent = litellm.sent("classify")
    assert ai["enabled"] is True and ai["calls"] == len(sent) >= 1 and ai["classified"] == ai["calls"]
    assert ai["stopped"] is None and ai["failed"] == 0 and ai["scope"] == "unclassified"
    assert ai["response_format"] == "json_schema" and ai["prompt_tokens"] > 0
    # Salida json_schema estricta con el enum de slugs del eje (G1).
    schema = sent[0].schema
    assert schema is not None and sent[0].response_format == "json_schema"
    values = schema["properties"]["domains"]["properties"]["values"]["items"]["properties"]["value"]
    assert set(values["enum"]) == {"facturas", "informes"}
    stored = db.get(ProjectContext, project.id)
    assert stored is not None and stored.ai_classification is True and stored.ai_classification_model
    docs = {d.path: d for d in db.scalars(select(ContextDocument).where(ContextDocument.project_id == project.id))}
    assert docs["receta.txt"].domain_slug == "informes" and docs["receta.txt"].classified_by == "ai"
    assert {d.classified_by for d in docs.values()} <= {"ai", "rules"}
    text = litellm.text_sent()
    assert str(migrated.locations_root) not in text and "harina" in text
    trail = _events(db, ctx.run_id) + json.dumps(result)
    assert KEY not in trail and BASE_URL not in trail
    # El total da contexto: la IA solo recibe lo que las reglas no clasificaron.
    expected = f"IA: {ai['calls']} de 4 documentos enviados (los que las reglas no clasificaron); {ai['classified']} clasificados"
    assert expected in trail


def test_rebuilding_without_changes_uses_the_ai_cache(
    run: Any, project: Project, db: Session, litellm: FakeLiteLLM
) -> None:
    """doc_organize 2.0 (M4): reconstruir sin cambios no vuelve a llamar al modelo."""
    litellm.answers["classify"] = classify_answer({"domains": ["informes"]})
    ctx, params = run(AI_DOMAINS)
    first = operation.run_build(ctx, params, project)
    calls = len(litellm.sent("classify"))
    _finish(db, ctx)

    ctx2, params2 = run(AI_DOMAINS)
    second = operation.run_build(ctx2, params2, project)

    assert first["ai"]["calls"] == calls >= 1
    assert second["ai"]["calls"] == 0 and second["ai"]["cached"] == calls
    assert len(litellm.sent("classify")) == calls
    assert "resueltos con la caché de IA" in _events(db, ctx2.run_id)


def test_build_falls_back_once_to_json_object(run: Any, project: Project, litellm: FakeLiteLLM) -> None:
    """Un modelo que no admite ``json_schema`` (400): el cliente cae una vez a ``json_object`` y lo recuerda."""
    litellm.json_schema = False
    litellm.answers["classify"] = classify_answer({"domains": ["informes"]})
    ctx, params = run(AI_DOMAINS)

    result = operation.run_build(ctx, params, project)

    formats = [r.response_format for r in litellm.sent("classify")]
    assert formats[:2] == ["json_schema", "json_object"] and formats.count("json_schema") == 1
    assert result["ai"]["response_format"] == "json_object" and result["ai"]["classified"] >= 1


def test_build_with_ai_enrichment_describes_the_classified_documents(
    run: Any, project: Project, db: Session, migrated: Settings, litellm: FakeLiteLLM
) -> None:
    """web 1.5.0 (doc_organize 1.5.0): descripción y palabras clave de la IA, marcadas en ``ai_filled``."""
    litellm.answers["enrich"] = lambda _: {"description": "Resumen de la IA.", "keywords": ["clave"]}
    ctx, params = run({**DOMAINS, "ai_enrichment": True})

    result = operation.run_build(ctx, params, project)

    enrichment = result["ai_enrichment"]
    assert enrichment["enabled"] is True and enrichment["calls"] == len(litellm.sent("enrich")) >= 1
    assert enrichment["applied"] == enrichment["calls"] and enrichment["failed"] == 0 and enrichment["stopped"] is None
    assert result["ai"] == {"enabled": False} and litellm.sent("classify") == []
    stored = db.get(ProjectContext, project.id)
    assert stored is not None and stored.ai_enrichment_model == "doc-organize-enrich"
    assert stored.ai_classification_model is None
    docs = list(db.scalars(select(ContextDocument).where(ContextDocument.project_id == project.id)))
    described = [d for d in docs if d.description == "Resumen de la IA."]
    assert described and all(
        d.keywords == ["clave"] and set(d.ai_filled) == {"description", "keywords"} for d in described
    )
    trail = _events(db, ctx.run_id) + json.dumps(result)
    assert KEY not in trail and BASE_URL not in trail
    assert "IA (descripciones):" in trail
    assert '"phase": "context_enrichment"' in trail  # su propia etapa en el progreso del run


def test_each_task_uses_its_model_and_key(
    run: Any, project: Project, db: Session, migrated: Settings, litellm: FakeLiteLLM, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D12: modelo y clave por tarea; sin clave propia, la general."""
    monkeypatch.setenv("DOC_ORGANIZE_LITELLM_MODEL_CLASSIFY", "clasificador-local")
    monkeypatch.setenv("DOC_ORGANIZE_LITELLM_MODEL_ENRICH", "descriptor-local")
    monkeypatch.setenv("DOC_ORGANIZE_LITELLM_VIRTUAL_KEY_ENRICH", ENRICH_KEY)
    litellm.answers["classify"] = classify_answer({"domains": ["informes"]})
    litellm.answers["enrich"] = lambda _: {"description": "Resumen.", "keywords": []}
    ctx, params = run({**AI_DOMAINS, "ai_enrichment": True})

    operation.run_build(ctx, params, project)

    assert {(r.body["model"], r.key) for r in litellm.sent("classify")} == {("clasificador-local", KEY)}
    assert {(r.body["model"], r.key) for r in litellm.sent("enrich")} == {("descriptor-local", ENRICH_KEY)}
    stored = db.get(ProjectContext, project.id)
    assert stored is not None
    assert (stored.ai_classification_model, stored.ai_enrichment_model) == ("clasificador-local", "descriptor-local")
    assert ENRICH_KEY not in _events(db, ctx.run_id)


def test_classification_and_enrichment_each_have_their_own_budget(
    run: Any, project: Project, migrated: Settings, litellm: FakeLiteLLM
) -> None:
    """Cada fase cuenta su propio presupuesto: con las dos activas y presupuesto 1, cada una envía como mucho uno."""
    litellm.answers["enrich"] = lambda _: {"description": "Resumen.", "keywords": []}
    litellm.answers["classify"] = classify_answer({})
    ctx, params = run({**AI_DOMAINS, "ai_enrichment": True})
    ctx.settings = migrated.model_copy(update={"ai_max_documents_per_run": 1})

    result = operation.run_build(ctx, params, project)

    assert result["ai"]["calls"] <= 1 and result["ai_enrichment"]["calls"] == 1
    assert result["ai_enrichment"]["stopped"] == "budget"


def test_task_budget_overrides_the_general_one(
    run: Any, project: Project, db: Session, migrated: Settings, litellm: FakeLiteLLM
) -> None:
    """Presupuesto por tarea (``budget_enrich`` en ``ai_settings``) en vez de ``ai_max_documents_per_run``."""
    db.add(AiSetting(family="litellm", field="budget_enrich", value="1"))
    db.commit()
    litellm.answers["enrich"] = lambda _: {"description": "Resumen.", "keywords": []}
    ctx, params = run({**DOMAINS, "ai_enrichment": True})

    result = operation.run_build(ctx, params, project)

    assert result["ai_enrichment"]["calls"] == 1 and result["ai_enrichment"]["stopped"] == "budget"


def test_build_stops_calling_after_a_rejected_key(
    run: Any, project: Project, db: Session, migrated: Settings, litellm: FakeLiteLLM
) -> None:
    litellm.keys = {"sk-otra"}
    ctx, params = run(AI_DOMAINS)

    result = operation.run_build(ctx, params, project)

    assert len(litellm.sent("classify")) == 1 and result["ai"]["stopped"] == "auth" and result["ai"]["failed"] == 1
    assert result["documents"] + result["unclassified"] == 4  # el contexto se construye igualmente
    events = _events(db, ctx.run_id)
    assert "rechazó la clave" in events and KEY not in events and BASE_URL not in events


def test_build_respects_the_budget(run: Any, project: Project, migrated: Settings, litellm: FakeLiteLLM) -> None:
    litellm.answers["classify"] = classify_answer({})
    ctx, params = run(AI_DOMAINS)
    ctx.settings = migrated.model_copy(update={"ai_max_documents_per_run": 1})

    result = operation.run_build(ctx, params, project)

    if result["ai"]["calls"]:  # solo si las reglas dejaron más de uno sin clasificar se llega al tope
        assert len(litellm.sent("classify")) == 1
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
    run: Any, project: Project, monkeypatch: pytest.MonkeyPatch, litellm: FakeLiteLLM
) -> None:
    ctx, params = run(AI_DOMAINS)
    monkeypatch.delenv("DOC_ORGANIZE_LITELLM_VIRTUAL_KEY")  # se quitó después de encolar

    with pytest.raises(JobFailed) as failure:
        operation.run_build(ctx, params, project)

    assert failure.value.code == "ai_not_configured"


DRAFT = {
    "domains": [
        {"slug": "facturas", "name": "Facturas", "description": "Facturas emitidas.", "keywords": ["iva"]},
        {"slug": "obras", "name": "Obras", "description": None, "keywords": []},
    ],
    "material_types": [{"slug": "informe", "name": "Informe", "description": None, "keywords": []}],
    "profile": {"context": "Proyecto sintético de pruebas.", "tie_breakers": None, "glossary": None},
    "reasoning": "Muestra sintética",
}


def test_taxonomy_draft_returns_the_markdown_without_saving(
    run: Any, project: Project, db: Session, migrated: Settings, litellm: FakeLiteLLM
) -> None:
    litellm.answers["taxonomy_design"] = lambda _: DRAFT
    ctx, params = run({"operation": "taxonomy_draft", "sample_size": 3})

    result = draft_operation.run(ctx, params, project)

    assert result["manifest_markdown"].startswith("---\nschema: 2\naxes:")  # manifiesto v2
    assert "Proyecto sintético de pruebas." in result["manifest_markdown"]  # perfil inicial en el cuerpo
    assert result["sample_documents"] == 3 and result["total_documents"] == 4
    assert [d["slug"] for d in result["domains"]] == ["facturas", "obras"]
    assert not (migrated.locations_root / "salidas" / "Proyecto A" / "taxonomy_manifest.md").exists()
    (sent,) = litellm.sent("taxonomy_design")
    assert sent.response_format == "json_schema" and sent.body["model"] == "doc-organize-taxonomy-design"
    prompt = sent.body["messages"][-1]["content"]  # el de sistema es de doc_organize (habla de «material de origen»)
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
        (lambda _: {**DRAFT, "domains": []}, "ai_error"),
        (lambda _: {**DRAFT, "reasoning": "x" * 300_000}, "ai_error"),  # mayor que un manifiesto
    ],
)
def test_taxonomy_draft_errors_carry_no_details(
    run: Any, project: Project, litellm: FakeLiteLLM, answer: Any, code: str
) -> None:
    litellm.answers["taxonomy_design"] = answer
    ctx, params = run({"operation": "taxonomy_draft"})

    with pytest.raises(JobFailed) as failure:
        draft_operation.run(ctx, params, project)

    assert failure.value.code == code and BASE_URL not in failure.value.message


def test_draft_has_its_own_timeout_and_no_retries(db: Session, migrated: Settings) -> None:
    """Hotfix 1.4.5: el borrador es una petición larga; el resto de tareas sigue con el plazo general."""
    settings = library_ai.ai_settings_for(ai_settings.connection(db, migrated, "litellm"))

    # doc_organize 2.0.0rc1: plazo y reintentos por tarea (TaskSettings.timeout_s/retries).
    assert (settings.timeout_for("taxonomy_design"), settings.retries_for("taxonomy_design")) == (300.0, 0)
    assert (settings.timeout_for("classify"), settings.retries_for("classify")) == (120.0, 2)


@pytest.mark.parametrize(
    ("error", "code", "timed_out"),
    [(httpx.ReadTimeout, "ai_timeout", True), (httpx.ConnectError, "ai_connection", False)],
)
def test_taxonomy_draft_tells_a_timeout_from_a_connection_error(
    run: Any,
    project: Project,
    litellm: FakeLiteLLM,
    caplog: pytest.LogCaptureFixture,
    error: type[httpx.TransportError],
    code: str,
    timed_out: bool,
) -> None:
    """Hotfix 1.4.5: un modelo lento no es «no se pudo conectar», no se reintenta y la causa queda en el log."""

    def _fail(_: dict[str, Any]) -> httpx.Response:
        raise error("sin respuesta")

    litellm.answers["taxonomy_design"] = _fail
    ctx, params = run({"operation": "taxonomy_draft"})

    with caplog.at_level("WARNING", logger=library_ai.__name__), pytest.raises(JobFailed) as failure:
        draft_operation.run(ctx, params, project)

    assert failure.value.code == code and len(litellm.sent("taxonomy_design")) == 1  # ai_draft_retries = 0
    assert ("300 s" in failure.value.message) is timed_out and BASE_URL not in failure.value.message
    (record,) = [r for r in caplog.records if r.name == library_ai.__name__]
    assert record.cause == error.__name__ and record.timed_out is timed_out  # type: ignore[attr-defined]
    logged = record.getMessage() + json.dumps({k: str(v) for k, v in vars(record).items()})
    assert KEY not in logged and BASE_URL not in logged


def test_taxonomy_draft_needs_converted_documents(
    run: Any, project: Project, migrated: Settings, litellm: FakeLiteLLM
) -> None:
    litellm.answers["taxonomy_design"] = lambda _: DRAFT
    shutil.rmtree(migrated.locations_root / "salidas" / "Proyecto A" / CONVERSION_DIR)
    ctx, params = run({"operation": "taxonomy_draft"})

    with pytest.raises(JobFailed) as failure:
        draft_operation.run(ctx, params, project)

    assert failure.value.code == "no_converted_documents" and litellm.requests == []


def test_chat_response_helper_is_valid_json() -> None:
    """El ayudante del proxy falso responde con el formato de ``/chat/completions`` que lee doc_organize."""
    assert json.loads(chat_response({"ok": True}).json()["choices"][0]["message"]["content"]) == {"ok": True}


def test_evidence_and_provenance_reach_the_api(
    run: Any, project: Project, litellm: FakeLiteLLM, user_client: TestClient, admin: Any
) -> None:
    """W3: la cita de la IA (y si se verificó) en el valor del eje y el prompt y modelo de la tarea en el contexto."""
    admin_client = login_as(user_client, admin.username, ADMIN_PASSWORD)
    assert admin_client.put("/api/v1/taxonomy-templates/ejes", json={"markdown": AXES_TEMPLATE}).status_code == 201
    litellm.answers["classify"] = classify_answer(
        {"domains": ["informes"], "material_types": ["original"]}, evidence="harina huevos azúcar"
    )
    ctx, params = run(
        {
            "operation": "context_build",
            "catalog": "template",
            "template_name": "ejes",
            "build_site": False,
            "ai_classification": True,
        }
    )

    operation.run_build(ctx, params, project)

    body = user_client.get(f"/api/v1/projects/{project.id}/context").json()
    (classify,) = [p for p in body["ai_provenance"] if p["task"] == "classify"]
    assert classify["model"] == "doc-organize-classify" and classify["source"] == "builtin" and classify["version"]
    page = user_client.get(f"/api/v1/projects/{project.id}/context/documents", params={"domain": "informes"}).json()
    (receta,) = [d for d in page["items"] if d["path"] == "receta.txt"]
    (value,) = receta["axes"]["domains"]
    assert value["classified_by"] == "ai" and value["evidence"] == "harina huevos azúcar"
    assert value["evidence_verified"] is True


def test_evidence_without_manifest(run: Any, project: Project, litellm: FakeLiteLLM, user_client: TestClient) -> None:
    """doc_organize 2.0.0rc1 (petición de W3): sin manifiesto, la cita del dominio que asigna la IA también se guarda."""
    litellm.answers["classify"] = classify_answer({"domains": ["informes"]}, evidence="harina huevos azúcar")
    ctx, params = run(AI_DOMAINS)

    operation.run_build(ctx, params, project)

    page = user_client.get(f"/api/v1/projects/{project.id}/context/documents", params={"domain": "informes"}).json()
    (receta,) = [d for d in page["items"] if d["path"] == "receta.txt"]
    (value,) = receta["axes"]["domains"]
    assert value["classified_by"] == "ai" and value["evidence"] == "harina huevos azúcar"
    assert value["evidence_verified"] is True
