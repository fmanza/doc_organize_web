"""API de IA (Fase 8): configuración cifrada sin secretos en claro, estado para cualquier usuario, panel de uso con
caché (clientes reales de doc_organize sobre ``httpx.MockTransport``) y comprobaciones al encolar."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.models import AiSetting, AuditEntry, Location, User
from app.domain.ai import usage as ai_usage
from app.integrations.doc_organize import ai as library_ai
from tests.conftest import ADMIN_PASSWORD, login_as, project_payload

KEY = "sk-api-test-secret-9z8y"
URL = "/api/v1/admin/ai-settings"
LITELLM = {"base_url": "https://litellm.example.internal", "virtual_key": KEY}


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Sin variables ``DOC_ORGANIZE_*`` del entorno de quien ejecuta los tests, y caché de uso vacía."""
    for family in library_ai.FAMILIES:
        for field in family.fields:
            monkeypatch.delenv(field.env_var, raising=False)
    ai_usage.clear_cache()
    yield
    ai_usage.clear_cache()


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
    assert user_client.put(f"{URL}/litellm_classification", json={"fields": {}}).status_code == 403
    assert user_client.get("/api/v1/admin/ai-usage").status_code == 403
    anonymous = TestClient(client.app, base_url="https://testserver")
    assert anonymous.get(URL).status_code == 401
    assert anonymous.get("/api/v1/ai/status").status_code == 401


def test_saved_secret_is_encrypted_and_never_returned(admin_api: TestClient, db: Session, fernet: str) -> None:
    response = admin_api.put(f"{URL}/litellm_classification", json={"fields": {**LITELLM, "model": "clasificador"}})

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
    assert set(entry.details["changed"]) == {"base_url", "virtual_key", "model"}  # type: ignore[index]
    assert "virtual_key" not in entry.details["values"]  # type: ignore[index,operator]


def test_clearing_falls_back_to_the_environment(
    admin_api: TestClient, fernet: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DOC_ORGANIZE_LITELLM_CLASSIFICATION_VIRTUAL_KEY", "env-key-1234")
    family = _family(admin_api.get(URL).json(), "litellm_classification")
    assert _field(family, "virtual_key")["source"] == "env" and family["configured"] is False  # falta base_url

    admin_api.put(f"{URL}/litellm_classification", json={"fields": LITELLM})
    response = admin_api.put(f"{URL}/litellm_classification", json={"fields": {"virtual_key": None, "model": ""}})

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
        ("github_copilot_usage", {"username": "no válido"}, 422, "ai_setting_invalid"),
        ("litellm_usage", {"virtual_key": "con espacio"}, 422, "ai_setting_invalid"),
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
    admin_api.put(f"{URL}/litellm_taxonomy_manifest_draft", json={"fields": LITELLM})

    status = user_client.get("/api/v1/ai/status")

    assert status.status_code == 200 and KEY not in status.text
    assert status.json()["families"]["litellm_taxonomy_manifest_draft"] is True
    assert status.json()["families"]["litellm_classification"] is False


def _usage_transport(monkeypatch: pytest.MonkeyPatch, handler: Callable[[httpx.Request], httpx.Response]) -> list[str]:
    seen: list[str] = []

    def _handle(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.host)
        return handler(request)

    monkeypatch.setattr(library_ai, "_transport", lambda _: httpx.MockTransport(_handle))
    return seen


def test_usage_panel_caches_and_isolates_sources(
    admin_api: TestClient, fernet: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.github.com":
            return httpx.Response(401)
        return httpx.Response(200, json={"info": {"spend": 1.25, "key_alias": "equipo"}})

    seen = _usage_transport(monkeypatch, _handler)
    admin_api.put(f"{URL}/litellm_usage", json={"fields": LITELLM})
    admin_api.put(
        f"{URL}/github_copilot_usage", json={"fields": {"username": "octo-cat", "pat": "ghp_fake_token_0001"}}
    )

    first = admin_api.get("/api/v1/admin/ai-usage")
    second = admin_api.get("/api/v1/admin/ai-usage?refresh=true")  # dentro del mínimo de 30 s: sigue la caché

    assert first.status_code == 200 and KEY not in first.text and "ghp_fake" not in first.text
    sources = {s["source"]: s for s in first.json()["sources"]}
    assert sources["litellm"]["total_cost_usd"] == 1.25 and sources["litellm"]["error"] is None
    assert sources["github_copilot"]["error"] == "ai_auth" and sources["github_copilot"]["items"] == []
    assert "raw" not in first.text
    assert len(seen) == 2
    assert all(s["cached"] for s in second.json()["sources"])


def test_usage_panel_without_configuration(admin_api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _usage_transport(monkeypatch, lambda _: httpx.Response(500))
    body = admin_api.get("/api/v1/admin/ai-usage").json()
    assert [s["configured"] for s in body["sources"]] == [False, False] and seen == []


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
        {"operation": "taxonomy_draft"},
    ):
        response = user_client.post(runs, json=body)
        assert response.status_code == 422 and response.json()["code"] == "ai_not_configured", body

    admin_api.put(f"{URL}/litellm_classification", json={"fields": LITELLM})
    admin_api.put(f"{URL}/litellm_taxonomy_manifest_draft", json={"fields": LITELLM})
    built = user_client.post(runs, json={"operation": "context_build", "ai_classification": True})
    assert built.status_code == 202, built.text
    assert KEY not in built.text and built.json()["params"]["ai_classification"] is True


def test_taxonomy_draft_roles(
    user_client: TestClient,
    admin_api: TestClient,
    project: dict[str, object],
    fernet: str,
    make_user: Callable[..., User],
) -> None:
    admin_api.put(f"{URL}/litellm_taxonomy_manifest_draft", json={"fields": LITELLM})
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
