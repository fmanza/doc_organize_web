"""API de IA (Fase 8; doc_organize 2.0 en W2): configuración cifrada sin secretos en claro (familia ``litellm`` con
modelo, clave y presupuesto por tarea), estado para cualquier usuario, panel de uso con caché (clientes reales de
doc_organize sobre ``httpx.MockTransport`` o el LiteLLM falso de ``tests/fake_litellm.py``) y comprobaciones al
encolar."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterator
from typing import Any

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.models import AiSetting, AuditEntry, Location, User
from app.domain.ai import connection_test
from app.domain.ai import usage as ai_usage
from app.integrations.doc_organize import ai as library_ai
from tests.conftest import ADMIN_PASSWORD, login_as, project_payload
from tests.fake_litellm import FakeLiteLLM

KEY = "sk-api-test-secret-9z8y"
URL = "/api/v1/admin/ai-settings"
LITELLM = {"base_url": "https://litellm.example.internal", "virtual_key": KEY}


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Sin variables ``DOC_ORGANIZE_*`` del entorno de quien ejecuta los tests, y caché de uso vacía."""
    for family in library_ai.FAMILIES:
        for field in family.fields:
            if field.env_var:
                monkeypatch.delenv(field.env_var, raising=False)
    for name in library_ai.legacy_env():
        monkeypatch.delenv(name, raising=False)
    ai_usage.clear_cache()
    connection_test.clear_rate_limit()
    yield
    ai_usage.clear_cache()
    connection_test.clear_rate_limit()


@pytest.fixture
def fernet(monkeypatch: pytest.MonkeyPatch, migrated: Settings) -> str:
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("DOW_FERNET_KEYS", key)
    get_settings.cache_clear()
    return key


@pytest.fixture
def admin_api(user_client: TestClient, admin: User) -> TestClient:
    """Admin en otro cliente: ``user_client`` sigue siendo el usuario normal (dueño de los proyectos)."""
    return login_as(user_client, admin.username, ADMIN_PASSWORD)


def _family(body: dict[str, object], key: str) -> dict[str, object]:
    return next(f for f in body["families"] if f["key"] == key)  # type: ignore[index,union-attr]


def _field(family: dict[str, object], name: str) -> dict[str, object]:
    return next(f for f in family["fields"] if f["name"] == name)  # type: ignore[index,union-attr]


def test_settings_are_admin_only(client: TestClient, user_client: TestClient, migrated: Settings) -> None:
    assert user_client.get(URL).status_code == 403
    assert user_client.put(f"{URL}/litellm", json={"fields": {}}).status_code == 403
    assert user_client.get("/api/v1/admin/ai-usage").status_code == 403
    anonymous = TestClient(client.app, base_url="https://testserver")
    assert anonymous.get(URL).status_code == 401
    assert anonymous.get("/api/v1/ai/status").status_code == 401


def test_saved_secret_is_encrypted_and_never_returned(admin_api: TestClient, db: Session, fernet: str) -> None:
    response = admin_api.put(f"{URL}/litellm", json={"fields": {**LITELLM, "model_classify": "clasificador"}})

    assert response.status_code == 200, response.text
    assert KEY not in response.text
    family = response.json()
    assert family["configured"] is True
    key = _field(family, "virtual_key")
    assert key["source"] == "db" and key["value"] is None and key["hint"] == "…9z8y"
    assert _field(family, "base_url")["value"] == LITELLM["base_url"]
    listing = admin_api.get(URL)
    assert KEY not in listing.text and listing.json()["encryption_configured"] is True
    rows = {row.field: row for row in db.scalars(select(AiSetting))}
    assert rows["virtual_key"].value is None and KEY not in (rows["virtual_key"].ciphertext or "")
    assert rows["base_url"].ciphertext is None
    entry = db.scalars(select(AuditEntry).where(AuditEntry.action == "ai_settings.update")).one()
    assert KEY not in str(entry.details)
    assert set(entry.details["changed"]) == {"base_url", "virtual_key", "model_classify"}  # type: ignore[index]
    assert "virtual_key" not in entry.details["values"]  # type: ignore[index,operator]


def test_clearing_falls_back_to_the_environment(
    admin_api: TestClient, fernet: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DOC_ORGANIZE_LITELLM_VIRTUAL_KEY", "env-key-1234")
    family = _family(admin_api.get(URL).json(), "litellm")
    assert _field(family, "virtual_key")["source"] == "env" and family["configured"] is False  # falta base_url

    admin_api.put(f"{URL}/litellm", json={"fields": LITELLM})
    response = admin_api.put(f"{URL}/litellm", json={"fields": {"virtual_key": None, "model_classify": ""}})

    key = _field(response.json(), "virtual_key")
    assert key["source"] == "env" and key["hint"] == "…1234"
    assert response.json()["configured"] is True


@pytest.mark.parametrize(
    ("family", "fields", "status", "code"),
    [
        ("desconocida", {}, 404, "ai_family_not_found"),
        ("litellm_usage", {"model": "x"}, 422, "ai_setting_invalid"),
        ("litellm_usage", {"base_url": "file:///etc/passwd"}, 422, "ai_setting_invalid"),
        ("litellm_usage", {"base_url": "https://u:p@litellm.example.internal"}, 422, "ai_setting_invalid"),
        ("github_copilot_usage", {"username": "octo-cat"}, 404, "ai_family_not_found"),  # quitada en la 2.1
        ("litellm_usage", {"virtual_key": "con espacio"}, 422, "ai_setting_invalid"),
        ("litellm_classification", {}, 404, "ai_family_not_found"),  # familias de 1.x: retiradas en 2.0
        ("litellm", {"model": "x"}, 422, "ai_setting_invalid"),  # el modelo va por tarea
        ("litellm", {"model_enrich": "no válido"}, 422, "ai_setting_invalid"),
        ("litellm", {"budget_classify": "0"}, 422, "ai_setting_invalid"),
        ("litellm", {"budget_enrich": "muchos"}, 422, "ai_setting_invalid"),
        ("litellm", {"budget_taxonomy_design": "5"}, 422, "ai_setting_invalid"),  # sin presupuesto: una petición
    ],
)
def test_invalid_updates_are_rejected(
    admin_api: TestClient, fernet: str, family: str, fields: dict[str, str], status: int, code: str
) -> None:
    response = admin_api.put(f"{URL}/{family}", json={"fields": fields})
    assert response.status_code == status and response.json()["code"] == code


def test_secrets_need_encryption(admin_api: TestClient, db: Session) -> None:
    assert admin_api.get(URL).json()["encryption_configured"] is False
    response = admin_api.put(f"{URL}/litellm_usage", json={"fields": LITELLM})
    assert response.status_code == 409 and response.json()["code"] == "encryption_not_configured"
    assert db.scalars(select(AiSetting)).first() is None  # nada a medias: tampoco la base_url
    ok = admin_api.put(f"{URL}/litellm_usage", json={"fields": {"base_url": LITELLM["base_url"]}})
    assert ok.status_code == 200


def test_rotated_away_key_reads_as_unconfigured(
    admin_api: TestClient, fernet: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    admin_api.put(f"{URL}/litellm_usage", json={"fields": LITELLM})
    monkeypatch.setenv("DOW_FERNET_KEYS", Fernet.generate_key().decode())
    get_settings.cache_clear()

    family = _family(admin_api.get(URL).json(), "litellm_usage")

    assert family["configured"] is False
    key = _field(family, "virtual_key")
    assert key["undecryptable"] is True and key["source"] == "none"


def test_status_is_visible_to_every_user(admin_api: TestClient, user_client: TestClient, fernet: str) -> None:
    assert set(user_client.get("/api/v1/ai/status").json()["tasks"].values()) == {False}
    admin_api.put(f"{URL}/litellm", json={"fields": LITELLM})

    status = user_client.get("/api/v1/ai/status")

    assert status.status_code == 200 and KEY not in status.text
    assert status.json()["families"] == {"litellm": True, "litellm_usage": False}
    assert status.json()["tasks"] == dict.fromkeys(("classify", "enrich", "taxonomy_design", "agent", "embed"), True)


def test_one_family_with_a_model_key_and_budget_per_task(admin_api: TestClient, db: Session, fernet: str) -> None:
    """2.0 (D12): la familia ``litellm`` lleva modelo, clave propia y presupuesto opcionales por tarea."""
    fields = {
        **LITELLM,
        "model_classify": "clasificador",
        "virtual_key_enrich": "sk-propia-enrich-5555",
        "budget_enrich": "25",
    }
    response = admin_api.put(f"{URL}/litellm", json={"fields": fields})

    assert response.status_code == 200, response.text
    family = response.json()
    assert "sk-propia-enrich-5555" not in response.text and _field(family, "virtual_key_enrich")["hint"] == "…5555"
    assert _field(family, "virtual_key_enrich")["task"] == "enrich" and _field(family, "virtual_key")["task"] is None
    assert _field(family, "budget_enrich")["value"] == "25" and _field(family, "budget_enrich")["env_var"] is None
    assert _field(family, "model_embed")["env_var"] == "DOC_ORGANIZE_LITELLM_MODEL_EMBED"
    assert {row.field for row in db.scalars(select(AiSetting))} == set(fields)


def test_legacy_environment_variables_are_reported(
    admin_api: TestClient,
    fernet: str,
    monkeypatch: pytest.MonkeyPatch,
    project: dict[str, object],
    user_client: TestClient,
) -> None:
    """D15/U17: las variables de 1.x ya no se leen; se listan (sin valores) y el error al encolar dice cuál usar."""
    monkeypatch.setenv("DOC_ORGANIZE_LITELLM_ENRICHMENT_MODEL", "modelo-antiguo")
    monkeypatch.setenv("DOC_ORGANIZE_LITELLM_CLASSIFICATION_VIRTUAL_KEY", "sk-antigua-0000")

    body = admin_api.get(URL).json()
    response = user_client.post(f"/api/v1/projects/{project['id']}/runs", json={"operation": "taxonomy_draft"})

    assert body["legacy_variables"] == [
        {
            "name": "DOC_ORGANIZE_LITELLM_CLASSIFICATION_VIRTUAL_KEY",
            "replacement": "DOC_ORGANIZE_LITELLM_VIRTUAL_KEY_CLASSIFY",
        },
        {"name": "DOC_ORGANIZE_LITELLM_ENRICHMENT_MODEL", "replacement": "DOC_ORGANIZE_LITELLM_MODEL_ENRICH"},
    ]
    assert "sk-antigua" not in json.dumps(body) and "modelo-antiguo" not in json.dumps(body)
    assert _family(body, "litellm")["configured"] is False  # no se leen
    assert response.status_code == 422 and response.json()["code"] == "ai_not_configured"
    assert "DOC_ORGANIZE_LITELLM_MODEL_ENRICH" in response.text and "sk-antigua" not in response.text


def _usage_transport(monkeypatch: pytest.MonkeyPatch, handler: Callable[[httpx.Request], httpx.Response]) -> list[str]:
    seen: list[str] = []

    def _handle(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.host)
        return handler(request)

    monkeypatch.setattr(library_ai, "_transport", lambda _: httpx.MockTransport(_handle))
    return seen


def test_usage_panel_caches_and_reports_the_key_budget(
    admin_api: TestClient, fernet: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _handler(request: httpx.Request) -> httpx.Response:
        info = {"spend": 1.25, "key_alias": "equipo", "max_budget": 10, "budget_reset_at": "2026-12-01T00:00:00Z"}
        return httpx.Response(200, json={"info": info})

    seen = _usage_transport(monkeypatch, _handler)
    admin_api.put(f"{URL}/litellm_usage", json={"fields": LITELLM})

    first = admin_api.get("/api/v1/admin/ai-usage")
    second = admin_api.get("/api/v1/admin/ai-usage?refresh=true")  # dentro del mínimo de 30 s: sigue la caché

    assert first.status_code == 200 and KEY not in first.text
    [source] = first.json()["sources"]  # 2.1: solo LiteLLM (sin GitHub Copilot)
    assert source["source"] == "litellm" and source["total_cost_usd"] == 1.25 and source["error"] is None
    assert source["budget"] == {
        "spend": 1.25,
        "max_budget": 10.0,
        "remaining": 8.75,
        "budget_reset_at": "2026-12-01T00:00:00Z",
    }
    assert "raw" not in first.text and "equipo" in first.text
    assert len(seen) == 1
    assert all(s["cached"] for s in second.json()["sources"])


def test_usage_panel_without_configuration(admin_api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _usage_transport(monkeypatch, lambda _: httpx.Response(500))
    body = admin_api.get("/api/v1/admin/ai-usage").json()
    assert [s["configured"] for s in body["sources"]] == [False] and seen == []


def test_usage_cache_expires(db: Session, fernet: str, admin_api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _usage_transport(monkeypatch, lambda _: httpx.Response(200, json={"spend": 2}))
    admin_api.put(f"{URL}/litellm_usage", json={"fields": LITELLM})
    now = [1000.0]

    ai_usage.usage(db, get_settings(), clock=lambda: now[0])
    now[0] += ai_usage.CACHE_SECONDS - 1
    ai_usage.usage(db, get_settings(), clock=lambda: now[0])
    now[0] += 2
    ai_usage.usage(db, get_settings(), clock=lambda: now[0])

    assert len(seen) == 2


# --- encolar con IA --------------------------------------------------------------------------------------------------


@pytest.fixture
def project(user_client: TestClient, project_locations: dict[str, Location]) -> dict[str, object]:
    response = user_client.post("/api/v1/projects", json=project_payload(project_locations, source_subpaths=["2024"]))
    assert response.status_code == 201, response.text
    return dict(response.json())


def test_ai_runs_need_their_family(
    user_client: TestClient, admin_api: TestClient, project: dict[str, object], fernet: str
) -> None:
    runs = f"/api/v1/projects/{project['id']}/runs"
    for body in (
        {"operation": "context_build", "ai_classification": True},
        {"operation": "context_build", "ai_enrichment": True},  # 1.5.0: tarea enrich
        {"operation": "taxonomy_draft"},
    ):
        response = user_client.post(runs, json=body)
        assert response.status_code == 422 and response.json()["code"] == "ai_not_configured", body

    admin_api.put(f"{URL}/litellm", json={"fields": LITELLM})
    built = user_client.post(runs, json={"operation": "context_build", "ai_classification": True})
    assert built.status_code == 202, built.text
    assert KEY not in built.text and built.json()["params"]["ai_classification"] is True


def test_one_family_serves_every_task(
    user_client: TestClient, admin_api: TestClient, project: dict[str, object], fernet: str
) -> None:
    """2.0: configurada la familia ``litellm``, clasificar, describir y el borrador se pueden encolar (sin modelo, el
    alias recomendado de cada tarea)."""
    runs = f"/api/v1/projects/{project['id']}/runs"
    admin_api.put(f"{URL}/litellm", json={"fields": LITELLM})

    built = user_client.post(
        runs, json={"operation": "context_build", "ai_classification": True, "ai_enrichment": True}
    )
    draft = user_client.post(runs, json={"operation": "taxonomy_draft"})

    assert built.status_code == 202, built.text
    assert built.json()["params"]["ai_enrichment"] is True and draft.status_code == 202


def test_taxonomy_draft_roles(
    user_client: TestClient,
    admin_api: TestClient,
    project: dict[str, object],
    fernet: str,
    make_user: Callable[..., User],
) -> None:
    admin_api.put(f"{URL}/litellm", json={"fields": LITELLM})
    runs = f"/api/v1/projects/{project['id']}/runs"
    viewer_user = make_user("lectora")
    user_client.post(f"/api/v1/projects/{project['id']}/members", json={"user_id": viewer_user.id, "role": "viewer"})
    viewer = login_as(user_client, "lectora")
    make_user("ajena")
    outsider = login_as(user_client, "ajena")

    assert viewer.post(runs, json={"operation": "taxonomy_draft"}).status_code == 403
    assert outsider.post(runs, json={"operation": "taxonomy_draft"}).status_code == 404
    assert user_client.post(runs, json={"operation": "taxonomy_draft", "sample_size": 61}).status_code == 422
    response = user_client.post(runs, json={"operation": "taxonomy_draft", "sample_size": 10})
    assert response.status_code == 202, response.text
    assert response.json()["is_write"] is False


def test_usage_never_logs_the_key(
    admin_api: TestClient, fernet: str, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """``LiteLLMUsageClient`` pone la clave en la *query* (``/key/info?key=…``) y httpx escribe cada URL en INFO."""
    configure_logging("DEBUG")
    _usage_transport(monkeypatch, lambda _: httpx.Response(200, json={"spend": 1}))
    admin_api.put(f"{URL}/litellm_usage", json={"fields": LITELLM})

    with caplog.at_level(logging.DEBUG):
        assert admin_api.get("/api/v1/admin/ai-usage").status_code == 200

    assert KEY not in caplog.text
    assert logging.getLogger("httpx").getEffectiveLevel() == logging.WARNING


# --- probar la conexión ---------------------------------------------------------------------------------------------

TEST = f"{URL}/litellm/test"
CHAT_OK = {"choices": [{"message": {"content": json.dumps({"ok": True})}}]}


def _probe(monkeypatch: pytest.MonkeyPatch, key_info: httpx.Response, chat: httpx.Response | None = None) -> list[str]:
    """Transporte que responde a ``/key/info`` y ``/chat/completions``; devuelve las rutas pedidas."""
    paths: list[str] = []

    def _handle(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path.endswith("/chat/completions"):
            return chat or httpx.Response(500)
        return key_info

    monkeypatch.setattr(library_ai, "_transport", lambda _: httpx.MockTransport(_handle))
    return paths


def _saved(db: Session) -> list[tuple[str, str]]:
    return [(row.family, row.field) for row in db.scalars(select(AiSetting))]


def test_probe_checks_the_key_without_spending_tokens(
    admin_api: TestClient, fernet: str, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _probe(monkeypatch, httpx.Response(200, json={"info": {"spend": 0, "models": ["clasificador"]}}))
    admin_api.put(f"{URL}/litellm", json={"fields": {**LITELLM, "model_classify": "clasificador"}})

    response = admin_api.post(TEST, json={})

    body = response.json()
    assert response.status_code == 200, response.text
    assert body["ok"] is True and body["error"] is None
    assert body["model_access"] == "ok" and body["model_checked"] is False
    assert paths == ["/key/info"]  # sin /chat/completions: no gasta tokens


def test_probe_uses_the_form_values_and_saves_nothing(
    admin_api: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sin nada guardado (ni cifrado configurado): se prueba lo escrito en el formulario y no se guarda."""
    _probe(monkeypatch, httpx.Response(200, json={"info": {"spend": 0}}))

    body = admin_api.post(TEST, json={"fields": LITELLM}).json()

    assert body["ok"] is True and body["model_access"] == "unknown"
    assert _saved(db) == []


@pytest.mark.parametrize(
    ("key_info", "error"),
    [(httpx.Response(401), "ai_auth"), (httpx.Response(502), "ai_error"), (None, "ai_connection")],
)
def test_probe_reports_the_kind_of_error(
    admin_api: TestClient, monkeypatch: pytest.MonkeyPatch, key_info: httpx.Response | None, error: str
) -> None:
    def _handle(request: httpx.Request) -> httpx.Response:
        if key_info is None:
            raise httpx.ConnectError("sin red", request=request)
        return key_info

    monkeypatch.setattr(library_ai, "_transport", lambda _: httpx.MockTransport(_handle))

    body = admin_api.post(TEST, json={"fields": LITELLM}).json()

    assert (body["ok"], body["error"]) == (False, error)


def test_probe_warns_when_the_key_cannot_use_the_model(admin_api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _probe(monkeypatch, httpx.Response(200, json={"info": {"models": ["otro-modelo"]}}))

    body = admin_api.post(TEST, json={"fields": {**LITELLM, "model_classify": "clasificador"}}).json()

    assert body["ok"] is True and body["model_access"] == "denied"


def test_model_check_sends_one_minimal_request(admin_api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = _probe(monkeypatch, httpx.Response(200, json={"info": {}}), httpx.Response(200, json=CHAT_OK))

    body = admin_api.post(TEST, json={"fields": LITELLM, "model_check": True}).json()

    assert body["ok"] is True and body["model_checked"] is True
    assert paths == ["/key/info", "/chat/completions"]


def test_a_missing_model_is_reported_as_such(admin_api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _probe(monkeypatch, httpx.Response(200, json={"info": {}}), httpx.Response(400, json={"error": "no existe"}))

    body = admin_api.post(TEST, json={"fields": {**LITELLM, "model_classify": "no-existe"}, "model_check": True}).json()

    assert (body["ok"], body["error"], body["model_checked"]) == (False, "ai_model", True)


def test_model_check_decides_when_key_info_is_forbidden(admin_api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Algunos proxies no dejan a la clave leer su /key/info: la prueba del modelo es la referencia."""
    _probe(monkeypatch, httpx.Response(403), httpx.Response(200, json=CHAT_OK))

    basic = admin_api.post(TEST, json={"fields": LITELLM}).json()
    connection_test.clear_rate_limit()
    with_model = admin_api.post(TEST, json={"fields": LITELLM, "model_check": True}).json()

    assert basic["error"] == "ai_auth"
    assert with_model["ok"] is True and with_model["model_checked"] is True


def test_the_saved_key_never_goes_to_another_url(
    admin_api: TestClient, fernet: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """S1: probar otra base_url con la clave guardada permitiría llevársela a un servidor propio."""
    hosts = _usage_transport(monkeypatch, lambda _: httpx.Response(200, json={"info": {}}))
    admin_api.put(f"{URL}/litellm", json={"fields": LITELLM})

    other = admin_api.post(TEST, json={"fields": {"base_url": "https://evil.example"}})
    same = admin_api.post(TEST, json={"fields": {"base_url": LITELLM["base_url"] + "/"}})  # misma URL normalizada
    connection_test.clear_rate_limit()
    typed = admin_api.post(TEST, json={"fields": {"base_url": "https://otro.example", "virtual_key": "sk-otra-0000"}})

    assert other.status_code == 422 and other.json()["code"] == "secret_required"
    assert same.status_code == 200
    assert typed.status_code == 200
    assert hosts == ["litellm.example.internal", "otro.example"]


def test_probe_is_rate_limited_per_family(admin_api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _probe(monkeypatch, httpx.Response(200, json={"info": {}}))

    first = admin_api.post(TEST, json={"fields": LITELLM})
    second = admin_api.post(TEST, json={"fields": LITELLM})
    other_family = admin_api.post(f"{URL}/litellm_usage/test", json={"fields": LITELLM})

    assert first.status_code == 200
    assert second.status_code == 429 and second.json()["code"] == "ai_test_too_soon"
    assert other_family.status_code == 200


def test_probe_validation_and_permissions(
    admin_api: TestClient, user_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _probe(monkeypatch, httpx.Response(200, json={"info": {}}))

    assert user_client.post(TEST, json={"fields": LITELLM}).status_code == 403
    assert admin_api.post(f"{URL}/nada/test", json={}).status_code == 404
    missing = admin_api.post(TEST, json={})
    assert missing.status_code == 422 and missing.json()["code"] == "ai_not_configured"
    bad_url = admin_api.post(TEST, json={"fields": {**LITELLM, "base_url": "ftp://x"}})
    assert bad_url.status_code == 422 and bad_url.json()["code"] == "ai_setting_invalid"
    usage_model = admin_api.post(f"{URL}/litellm_usage/test", json={"fields": LITELLM, "model_check": True})
    assert usage_model.status_code == 422 and usage_model.json()["code"] == "ai_setting_invalid"
    assert paths == []


def test_github_copilot_is_gone_and_its_variables_are_reported(
    admin_api: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """2.1: sin familia de GitHub Copilot; si sus variables siguen definidas, se avisa sin valores y sin sustituta."""
    hosts = _usage_transport(monkeypatch, lambda _: httpx.Response(401))
    monkeypatch.setenv("DOC_ORGANIZE_GITHUB_PAT", "ghp_fake_token_0001")

    probe = admin_api.post(
        f"{URL}/github_copilot_usage/test", json={"fields": {"username": "octo-cat", "pat": "ghp_fake_token_0001"}}
    )
    settings = admin_api.get(URL).json()

    assert probe.status_code == 404 and hosts == []
    assert "github_copilot_usage" not in [family["key"] for family in settings["families"]]
    assert {"name": "DOC_ORGANIZE_GITHUB_PAT", "replacement": None} in settings["legacy_variables"]
    assert "ghp_fake" not in admin_api.get(URL).text


def test_probe_never_leaks_the_key(
    admin_api: TestClient,
    fernet: str,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """S3: ni en la respuesta, ni en los logs, ni en la auditoría (que tampoco guarda la URL)."""
    configure_logging("DEBUG")
    _probe(monkeypatch, httpx.Response(401), httpx.Response(200, json=CHAT_OK))

    with caplog.at_level(logging.DEBUG):
        response = admin_api.post(TEST, json={"fields": LITELLM, "model_check": True})

    entry = db.scalars(select(AuditEntry).where(AuditEntry.action == "ai_settings.test")).one()
    assert KEY not in response.text and KEY not in caplog.text
    assert KEY not in json.dumps(entry.details) and "litellm.example" not in json.dumps(entry.details)
    assert entry.details == {
        "model_check": True,
        "task": "classify",
        "error": None,
        "form_fields": ["base_url", "virtual_key"],
    }


def test_model_check_reports_json_schema_support_per_task(
    admin_api: TestClient, fernet: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """2.0 (U9): «Probar el modelo» de una tarea usa su modelo y su clave, y dice si admite ``json_schema`` estricto."""
    proxy = FakeLiteLLM(keys={KEY, "sk-propia-enrich-5555"}).install(monkeypatch)
    admin_api.put(
        f"{URL}/litellm",
        json={"fields": {**LITELLM, "model_enrich": "descriptor", "virtual_key_enrich": "sk-propia-enrich-5555"}},
    )

    strict = admin_api.post(TEST, json={"model_check": True, "task": "enrich"}).json()
    connection_test.clear_rate_limit()
    proxy.json_schema = False
    fallback = admin_api.post(TEST, json={"model_check": True}).json()

    assert (strict["ok"], strict["task"], strict["response_format"]) == (True, "enrich", "json_schema")
    assert (fallback["ok"], fallback["task"], fallback["response_format"]) == (True, "classify", "json_object")
    enrich = proxy.sent("enrich")
    assert [(r.body["model"], r.key) for r in enrich] == [("descriptor", "sk-propia-enrich-5555")]
    assert [r.body["model"] for r in proxy.sent("classify")] == ["doc-organize-classify", "doc-organize-classify"]


def test_model_check_of_embeddings(admin_api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    proxy = FakeLiteLLM(keys={KEY}).install(monkeypatch)

    body = admin_api.post(TEST, json={"fields": LITELLM, "model_check": True, "task": "embed"}).json()

    assert (body["ok"], body["task"], body["response_format"]) == (True, "embed", None)
    assert [r.path for r in proxy.requests] == ["/key/info", "/embeddings"]


def test_task_keys_never_go_to_another_url(admin_api: TestClient, fernet: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """S1 con claves por tarea: con otra URL basta escribir la general; las guardadas de cada tarea no se envían."""
    proxy = FakeLiteLLM(keys={"sk-otra-0000"}).install(monkeypatch)
    admin_api.put(f"{URL}/litellm", json={"fields": {**LITELLM, "virtual_key_classify": "sk-propia-classify-7777"}})

    body = admin_api.post(
        TEST, json={"fields": {"base_url": "https://otro.example", "virtual_key": "sk-otra-0000"}, "model_check": True}
    ).json()

    assert body["ok"] is True
    assert {r.key for r in proxy.requests} == {"sk-otra-0000"}


@pytest.mark.parametrize(("model_check", "timeout"), [(False, 10.0), (True, 60.0)])
def test_model_check_waits_for_a_model_that_is_loading(
    admin_api: TestClient, monkeypatch: pytest.MonkeyPatch, model_check: bool, timeout: float
) -> None:
    """Un modelo local descargado de memoria tarda más de 10 s en responder: «Probar el modelo» espera hasta 60 s."""
    seen: list[float] = []
    original = connection_test.check_connection

    def _check(connection: Any, **kwargs: Any) -> Any:
        seen.append(connection.timeout_s)
        return original(connection, **kwargs)

    _probe(monkeypatch, httpx.Response(200, json={"info": {}}), httpx.Response(200, json=CHAT_OK))
    monkeypatch.setattr(connection_test, "check_connection", _check)

    admin_api.post(TEST, json={"fields": LITELLM, "model_check": model_check})

    assert seen == [timeout]
