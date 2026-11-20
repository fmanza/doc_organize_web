"""Diagnóstico del entorno (W4, ``check_environment``): solo el admin de instancia, en un subproceso, sin claves, URL
del proxy ni rutas del contenedor en la respuesta; uno cada 30 s; auditado sin detalles."""

from __future__ import annotations

import json
from typing import Any

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import AuditEntry, User
from app.domain.ai import diagnostics
from app.integrations.doc_organize import ai as library_ai
from app.integrations.doc_organize.diagnostics import DiagnosticCheck, DiagnosticsReport, _clean
from tests.conftest import ADMIN_PASSWORD, login_as

URL = "/api/v1/admin/diagnostics"
KEY = "sk-diagnostics-secret-4r5t"
BASE_URL = "https://litellm.example.internal"


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch: pytest.MonkeyPatch) -> None:
    for family in library_ai.FAMILIES:
        for field in family.fields:
            if field.env_var:
                monkeypatch.delenv(field.env_var, raising=False)
    diagnostics.clear_rate_limit()


@pytest.fixture
def admin_api(user_client: TestClient, admin: User) -> TestClient:
    return login_as(user_client, admin.username, ADMIN_PASSWORD)


def test_runs_check_environment_in_a_subprocess(admin_api: TestClient, db: Session, migrated: Settings) -> None:
    response = admin_api.post(URL, json={})

    assert response.status_code == 200, response.text
    body = response.json()
    names = [check["name"] for check in body["checks"]]
    assert names[0] == "python" and "docling" in names and not any(name.startswith("ai") for name in names)
    assert all(check["status"] in ("ok", "warning", "error") for check in body["checks"])
    assert str(migrated.data_dir) not in response.text
    entry = db.scalars(select(AuditEntry).where(AuditEntry.action == "admin.diagnostics")).one()
    assert entry.details["check_ai"] is False and set(entry.details) == {"check_ai", "ok", "errors"}  # type: ignore[index,arg-type]


def test_only_the_instance_admin_and_rate_limited(
    user_client: TestClient, admin_api: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = DiagnosticsReport(checks=[DiagnosticCheck("python", "ok", "Python 3.12")], checked_at="2026-11-20T00:00:00Z")
    monkeypatch.setattr(diagnostics, "run_diagnostics", lambda **_: fake)

    assert user_client.post(URL, json={}).status_code == 403
    assert admin_api.post(URL, json={}).status_code == 200
    again = admin_api.post(URL, json={})
    assert again.status_code == 429 and again.json()["code"] == "diagnostics_too_soon"


def test_ai_check_uses_each_task_model_and_key_without_leaking(
    admin_api: TestClient, monkeypatch: pytest.MonkeyPatch, migrated: Settings
) -> None:
    monkeypatch.setenv("DOW_FERNET_KEYS", Fernet.generate_key().decode())
    get_settings.cache_clear()
    admin_api.put(
        "/api/v1/admin/ai-settings/litellm",
        json={
            "fields": {
                "base_url": BASE_URL,
                "virtual_key": KEY,
                "model_enrich": "descriptor",
                "virtual_key_enrich": "sk-enrich-9i8u",
                "model_embed": "vectores",
            }
        },
    )
    seen: dict[str, Any] = {}

    def _run(**kwargs: Any) -> DiagnosticsReport:
        seen.update(kwargs)
        detail = f"Error de {BASE_URL} con {KEY} en {migrated.data_dir}"  # lo que nunca debe salir
        return DiagnosticsReport(
            checks=[DiagnosticCheck("ai:classify", "error", _clean(detail, [*kwargs["redact"], BASE_URL, KEY]) or "")],
            checked_at="2026-11-20T00:00:00Z",
        )

    monkeypatch.setattr(diagnostics, "run_diagnostics", _run)

    response = admin_api.post(URL, json={"check_ai": True})

    assert response.status_code == 200, response.text
    endpoints = {e.name: (e.model, e.virtual_key, e.kind) for e in seen["endpoints"]}
    assert endpoints == {
        "classify": ("doc-organize-classify", KEY, "chat"),
        "enrich": ("descriptor", "sk-enrich-9i8u", "chat"),
        "taxonomy_design": ("doc-organize-taxonomy-design", KEY, "chat"),
        "embed": ("vectores", KEY, "embedding"),  # rc2: con modelo propio, se pide un vector
    }
    text = json.dumps(response.json())
    assert KEY not in text and BASE_URL not in text and str(migrated.data_dir) not in text
    assert response.json()["ok"] is False


def test_clean_hides_every_secret() -> None:
    assert _clean("a https://x.example/v1 b sk-1 c", ["https://x.example", "sk-1"]) == "a «oculto»/v1 b «oculto» c"
    assert _clean(None, ["x"]) is None
