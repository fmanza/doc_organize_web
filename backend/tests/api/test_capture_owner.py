"""web 1.5.0 (doc_organize 1.5.0): «guardar el propietario de cada fichero», ajuste fijo del proyecto que solo cambia
el ``owner`` y que el run copia al encolar (el valor del cliente se descarta)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import AuditEntry, Location, User
from tests.conftest import login_as, project_payload


@pytest.fixture
def project(user_client: TestClient, project_locations: dict[str, Location], migrated: Settings) -> dict[str, object]:
    (migrated.locations_root / "origen" / "2024").mkdir(parents=True, exist_ok=True)
    response = user_client.post("/api/v1/projects", json=project_payload(project_locations))
    assert response.status_code == 201, response.text
    return dict(response.json())


def _url(project: dict[str, object]) -> str:
    return f"/api/v1/projects/{project['id']}"


def test_projects_start_without_capturing_the_owner(user_client: TestClient, project: dict[str, object]) -> None:
    assert project["capture_owner"] is False
    assert user_client.get(_url(project)).json()["capture_owner"] is False


def test_the_owner_turns_it_on_and_it_is_audited(
    user_client: TestClient, project: dict[str, object], db: Session
) -> None:
    response = user_client.patch(_url(project), json={"capture_owner": True})

    assert response.status_code == 200, response.text
    assert response.json()["capture_owner"] is True
    entries = db.scalars(select(AuditEntry).where(AuditEntry.target_id == str(project["id"]))).all()
    assert any((entry.details or {}).get("fields") == ["capture_owner"] for entry in entries)


@pytest.mark.parametrize("role", ["viewer", "editor"])
def test_only_the_owner_changes_it(
    user_client: TestClient, project: dict[str, object], make_user: Callable[..., User], role: str
) -> None:
    member = make_user("miembro")
    added = user_client.post(f"{_url(project)}/members", json={"user_id": member.id, "role": role})
    assert added.status_code == 201, added.text

    assert login_as(user_client, "miembro").patch(_url(project), json={"capture_owner": True}).status_code == 403


def test_the_run_ignores_what_the_client_sends(user_client: TestClient, project: dict[str, object]) -> None:
    response = user_client.post(f"{_url(project)}/runs", json={"operation": "scan", "capture_owner": True})

    assert response.status_code == 202, response.text
    assert response.json()["params"]["capture_owner"] is False


def test_the_run_copies_the_project_setting(user_client: TestClient, project: dict[str, object]) -> None:
    assert user_client.patch(_url(project), json={"capture_owner": True}).status_code == 200

    response = user_client.post(f"{_url(project)}/runs", json={"operation": "scan"})

    assert response.status_code == 202, response.text
    assert response.json()["params"]["capture_owner"] is True


def test_the_setting_does_not_reach_the_source_folder(project: dict[str, object], migrated: Settings) -> None:
    """Es un ajuste de la base de la web: no escribe nada en el origen."""
    assert not any(Path(migrated.locations_root / "origen").rglob("*.json"))
