"""Redacción de credenciales por proyecto (W4, D7): el ajuste se edita por la API (editor con destino ``rw``,
auditado) y llega a la librería: a lo que sale hacia la IA (``AiSettings.redact_credentials``) y al sitio
(``SiteGenerator.generate(redact_credentials=)``). Credenciales y documentos sintéticos."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest
from doc_organize import SiteGenerator
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import AuditEntry, Location, Project, User
from app.integrations.doc_organize import ai as library_ai
from app.jobs.operations import context as operation
from tests.conftest import login_as
from tests.fake_litellm import FakeLiteLLM, classify_answer
from tests.jobs.test_context_operation import DOMAINS

KEY = "sk-redaction-test-1q2w"
#: Credencial sintética con forma de clave de API (la detecta la redacción de doc_organize).
SECRET = "password=SinteticaNoReal123"


@pytest.fixture(autouse=True)
def _ai_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for family in library_ai.FAMILIES:
        for field in family.fields:
            if field.env_var:
                monkeypatch.delenv(field.env_var, raising=False)
    monkeypatch.setenv("DOC_ORGANIZE_LITELLM_BASE_URL", "https://litellm.example.internal")
    monkeypatch.setenv("DOC_ORGANIZE_LITELLM_VIRTUAL_KEY", KEY)


def _with_secret(migrated: Settings) -> None:
    """La receta sintética lleva una credencial en su texto convertido (la IA la recibe: las reglas no la clasifican)."""
    conversion = migrated.locations_root / "salidas" / "Proyecto A" / "Conversión"
    for json_path in conversion.rglob("receta*.json"):
        data = json.loads(json_path.read_text(encoding="utf-8"))
        data["chunks"][0]["text"] += f" {SECRET}"
        json_path.write_text(json.dumps(data), encoding="utf-8")


def test_settings_api_permissions_and_audit(
    user_client: TestClient,
    project: Project,
    make_user: Callable[..., User],
    db: Session,
) -> None:
    url = f"/api/v1/projects/{project.id}/ai-settings"
    assert user_client.get(f"/api/v1/projects/{project.id}").json()["ai_redact_credentials"] is True  # D7
    viewer_user = make_user("lectora")
    editor_user = make_user("editora")
    for user, role in ((viewer_user, "viewer"), (editor_user, "editor")):
        user_client.post(f"/api/v1/projects/{project.id}/members", json={"user_id": user.id, "role": role})

    assert login_as(user_client, "lectora").put(url, json={"ai_redact_credentials": False}).status_code == 403
    response = login_as(user_client, "editora").put(url, json={"ai_redact_credentials": False})

    assert response.status_code == 200, response.text
    assert response.json()["ai_redact_credentials"] is False
    entry = db.scalars(select(AuditEntry).where(AuditEntry.action == "project.ai_settings_update")).one()
    assert entry.details == {"ai_redact_credentials": [True, False]}


def test_read_only_destination_rejects_the_change(user_client: TestClient, project: Project, db: Session) -> None:
    db.execute(update(Location).where(Location.id == project.destination_location_id).values(access="ro"))
    db.commit()

    response = user_client.put(f"/api/v1/projects/{project.id}/ai-settings", json={"ai_redact_credentials": False})

    assert response.status_code == 422 and response.json()["code"] == "location_read_only"


@pytest.mark.parametrize("redact", [True, False])
def test_the_setting_reaches_the_ai_and_the_site(
    run: Any,
    project: Project,
    db: Session,
    migrated: Settings,
    monkeypatch: pytest.MonkeyPatch,
    redact: bool,
) -> None:
    _with_secret(migrated)
    db.execute(update(Project).where(Project.id == project.id).values(ai_redact_credentials=redact))
    db.commit()
    project.ai_redact_credentials = redact  # el worker carga el proyecto de la BD; el de la fixture está desligado
    proxy = FakeLiteLLM(keys={KEY}).install(monkeypatch)
    proxy.answers["classify"] = classify_answer({"domains": ["informes"]})
    seen: list[bool] = []
    original = SiteGenerator.generate

    async def _generate(self: SiteGenerator, *args: Any, **kwargs: Any) -> Any:
        seen.append(kwargs.get("redact_credentials", True))
        return await original(self, *args, **kwargs)

    monkeypatch.setattr(SiteGenerator, "generate", _generate)
    ctx, params = run({**DOMAINS, "ai_classification": True, "build_site": True})

    operation.run_build(ctx, params, project)

    sent = proxy.text_sent()
    assert proxy.sent("classify")
    assert (SECRET in sent) is not redact
    assert ("REDACTADO" in sent) is redact
    assert seen == [redact]
