"""Proyectos y miembros (Fase 3): alta con carpeta propia, acceso por miembros, IDOR y solapes."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import AuditEntry, Location, User
from tests.conftest import ADMIN_PASSWORD, login_as, project_payload


@pytest.fixture
def project(user_client: TestClient, project_locations: dict[str, Location]) -> dict[str, object]:
    response = user_client.post("/api/v1/projects", json=project_payload(project_locations))
    assert response.status_code == 201, response.text
    body: dict[str, object] = response.json()
    return body


def test_user_creates_project_as_owner_with_new_folder(
    project: dict[str, object], migrated: Settings, db: Session
) -> None:
    assert project["role"] == "owner"
    assert project["source_subpaths"] == ["2024"]
    assert project["destination_subpath"] == "Proyecto A"
    assert (migrated.locations_root / "salidas" / "Proyecto A").is_dir()
    assert (migrated.data_dir / "projects" / str(project["id"])).is_dir()
    assert "container_path" not in str(project)
    assert db.scalar(select(AuditEntry).where(AuditEntry.action == "project.create")) is not None


def test_create_with_existing_empty_folder(
    user_client: TestClient, project_locations: dict[str, Location], migrated: Settings
) -> None:
    (migrated.locations_root / "salidas" / "vacia").mkdir()
    payload = project_payload(project_locations, destination_parent="vacia", new_folder=None)

    response = user_client.post("/api/v1/projects", json=payload)

    assert response.status_code == 201, response.text
    assert response.json()["destination_subpath"] == "vacia"


def test_existing_folder_must_be_empty(
    user_client: TestClient, project_locations: dict[str, Location], migrated: Settings
) -> None:
    (migrated.locations_root / "salidas" / "llena").mkdir()
    (migrated.locations_root / "salidas" / "llena" / "ajeno.txt").write_text("x", encoding="utf-8")

    response = user_client.post(
        "/api/v1/projects", json=project_payload(project_locations, destination_parent="llena", new_folder=None)
    )

    assert response.status_code == 409
    assert response.json()["code"] == "folder_not_empty"


def test_location_root_is_not_a_project_folder(user_client: TestClient, project_locations: dict[str, Location]) -> None:
    response = user_client.post("/api/v1/projects", json=project_payload(project_locations, new_folder=None))

    assert response.status_code == 400


def test_new_folder_that_exists_conflicts_and_is_not_touched(
    user_client: TestClient, project_locations: dict[str, Location], migrated: Settings
) -> None:
    existing = migrated.locations_root / "salidas" / "Proyecto A"
    existing.mkdir()
    (existing / "ajeno.txt").write_text("x", encoding="utf-8")

    response = user_client.post("/api/v1/projects", json=project_payload(project_locations))

    assert response.status_code == 409
    assert (existing / "ajeno.txt").is_file()


@pytest.mark.parametrize("bad", ["../fuera", "/etc", "a\\b", "C:/x", "no-existe"])
def test_source_paths_go_through_resolver(
    user_client: TestClient, project_locations: dict[str, Location], bad: str
) -> None:
    response = user_client.post("/api/v1/projects", json=project_payload(project_locations, source_subpaths=[bad]))

    assert response.status_code in (400, 404)
    assert "container_path" not in response.text and "mnt" not in response.text


def test_source_must_be_source_and_destination_rw(
    user_client: TestClient, project_locations: dict[str, Location]
) -> None:
    swapped = project_payload(project_locations)
    swapped["source_location_id"], swapped["destination_location_id"] = (
        project_locations["destination"].id,
        project_locations["source"].id,
    )

    assert user_client.post("/api/v1/projects", json=swapped).status_code == 400


def test_invalid_new_folder_name(user_client: TestClient, project_locations: dict[str, Location]) -> None:
    response = user_client.post("/api/v1/projects", json=project_payload(project_locations, new_folder="CON"))

    assert response.status_code == 400


def test_output_cannot_overlap_source_in_same_location(admin_client: TestClient, migrated: Settings) -> None:
    (migrated.locations_root / "ambas" / "docs").mkdir(parents=True)
    loc = admin_client.post(
        "/api/v1/locations", json={"name": "Ambas", "path": "ambas", "usage": "both", "access": "rw"}
    ).json()
    payload = {
        "name": "Solape",
        "source_location_id": loc["id"],
        "source_subpaths": ["docs"],
        "destination_location_id": loc["id"],
        "destination_parent": "docs",
        "new_folder": "salida",
    }

    assert admin_client.post("/api/v1/projects", json=payload).status_code == 400


def test_two_projects_cannot_share_outputs(
    user_client: TestClient, project: dict[str, object], project_locations: dict[str, Location]
) -> None:
    payload = project_payload(project_locations, name="Otro", destination_parent="Proyecto A", new_folder="dentro")

    response = user_client.post("/api/v1/projects", json=payload)

    assert response.status_code == 409


def test_duplicate_name_conflicts(
    user_client: TestClient, project: dict[str, object], project_locations: dict[str, Location]
) -> None:
    payload = project_payload(project_locations, name="proyecto a")
    payload["new_folder"] = "otra"

    assert user_client.post("/api/v1/projects", json=payload).status_code == 409


# --- acceso ------------------------------------------------------------------------------------------------------


def test_non_member_gets_404_everywhere(user_client: TestClient, project: dict[str, object], make_user: object) -> None:
    make_user("intrusa")  # type: ignore[operator]
    other = login_as(user_client, "intrusa")
    pid = project["id"]

    assert other.get("/api/v1/projects").json()["total"] == 0
    for method, path in [
        ("GET", f"/api/v1/projects/{pid}"),
        ("PATCH", f"/api/v1/projects/{pid}"),
        ("GET", f"/api/v1/projects/{pid}/members"),
        ("POST", f"/api/v1/projects/{pid}/runs"),
    ]:
        response = other.request(method, path, json={"operation": "noop"} if method == "POST" else {})
        assert response.status_code == 404, (method, path)


def test_admin_sees_every_project_as_owner(admin_client: TestClient, project: dict[str, object]) -> None:
    listed = admin_client.get("/api/v1/projects").json()

    assert listed["total"] == 1
    assert listed["items"][0]["role"] == "owner"


def test_owner_renames_only_in_db(user_client: TestClient, project: dict[str, object], migrated: Settings) -> None:
    response = user_client.patch(f"/api/v1/projects/{project['id']}", json={"name": "Renombrado"})

    assert response.status_code == 200
    assert response.json()["name"] == "Renombrado"
    assert (migrated.locations_root / "salidas" / "Proyecto A").is_dir()


def test_owner_changes_sources(user_client: TestClient, project: dict[str, object]) -> None:
    response = user_client.patch(
        f"/api/v1/projects/{project['id']}", json={"source_subpaths": ["2025", "2024", "2024"]}
    )

    assert response.status_code == 200
    assert response.json()["source_subpaths"] == ["2024", "2025"]


def test_members_roles_and_last_owner(
    user_client: TestClient, project: dict[str, object], make_user: object, user: User
) -> None:
    bea = make_user("bea")  # type: ignore[operator]
    pid = project["id"]

    added = user_client.post(f"/api/v1/projects/{pid}/members", json={"user_id": bea.id, "role": "viewer"})
    assert added.status_code == 201
    assert user_client.post(f"/api/v1/projects/{pid}/members", json={"user_id": bea.id}).status_code == 409

    viewer = login_as(user_client, "bea")
    assert viewer.get(f"/api/v1/projects/{pid}").json()["role"] == "viewer"
    assert viewer.patch(f"/api/v1/projects/{pid}", json={"name": "X"}).status_code == 403
    assert viewer.post(f"/api/v1/projects/{pid}/runs", json={"operation": "noop"}).status_code == 403

    assert user_client.delete(f"/api/v1/projects/{pid}/members/{user.id}").status_code == 409
    assert user_client.patch(f"/api/v1/projects/{pid}/members/{user.id}", json={"role": "editor"}).status_code == 409
    assert user_client.patch(f"/api/v1/projects/{pid}/members/{bea.id}", json={"role": "editor"}).status_code == 200
    assert viewer.post(f"/api/v1/projects/{pid}/runs", json={"operation": "noop"}).status_code == 202
    assert user_client.delete(f"/api/v1/projects/{pid}/members/{bea.id}").status_code == 204
    assert viewer.get(f"/api/v1/projects/{pid}").status_code == 404


def test_cannot_add_inactive_or_unknown_user(user_client: TestClient, project: dict[str, object]) -> None:
    response = user_client.post(f"/api/v1/projects/{project['id']}/members", json={"user_id": 999})

    assert response.status_code == 404


def test_user_lookup_returns_active_users_only(
    user_client: TestClient, make_user: object, admin_client: TestClient
) -> None:
    carla = make_user("carla")  # type: ignore[operator]
    make_user("carlos")  # type: ignore[operator]
    admin_client.patch(f"/api/v1/users/{carla.id}", json={"is_active": False})

    found = user_client.get("/api/v1/users/lookup", params={"q": "car"}).json()["items"]

    assert [u["username"] for u in found] == ["carlos"]
    assert set(found[0]) == {"id", "username", "display_name"}


def test_location_in_use_cannot_be_deleted(
    user_client: TestClient, project: dict[str, object], project_locations: dict[str, Location], admin: User
) -> None:
    admin_session = login_as(user_client, admin.username, ADMIN_PASSWORD)

    response = admin_session.delete(f"/api/v1/locations/{project_locations['source'].id}")

    assert response.status_code == 409


def test_unauthenticated_requests_get_401(client: TestClient) -> None:
    assert client.get("/api/v1/projects").status_code == 401
    assert client.get("/api/v1/runs").status_code == 401


def test_folder_created_is_removed_if_project_fails(
    user_client: TestClient, project_locations: dict[str, Location], migrated: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.domain.projects import service

    def boom(*_: object, **__: object) -> Path:
        raise RuntimeError("fallo simulado")

    monkeypatch.setattr(service, "state_dir", boom)

    response = user_client.post("/api/v1/projects", json=project_payload(project_locations))

    assert response.status_code == 500
    assert not (migrated.locations_root / "salidas" / "Proyecto A").exists()
