"""Ubicaciones, explorador, montajes, ajustes administrables, capacidades y salud (Fase 2)."""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import AuditEntry, User
from app.integrations.doc_organize import Capabilities, CapabilitiesSnapshot, capabilities_cache
from tests.conftest import USER_PASSWORD, do_login

LOCATION = {"name": "Expedientes", "path": "expedientes", "usage": "source", "access": "ro", "kind": "network"}


@pytest.fixture
def mnt(migrated: Settings) -> Path:
    """``DOW_LOCATIONS_ROOT`` con ``expedientes/{2024/enero, 2025}`` y ``salidas``."""
    root = migrated.locations_root
    (root / "expedientes" / "2024" / "enero").mkdir(parents=True)
    (root / "expedientes" / "2025").mkdir()
    (root / "expedientes" / "nota.txt").write_text("x", encoding="utf-8")
    (root / "salidas").mkdir()
    return root


@pytest.fixture
def location(admin_client: TestClient, mnt: Path) -> dict[str, object]:
    response = admin_client.post("/api/v1/locations", json=LOCATION)
    assert response.status_code == 201, response.text
    body: dict[str, object] = response.json()
    return body


def _as_user(admin_client: TestClient, user: User) -> TestClient:
    other = TestClient(admin_client.app, base_url="https://testserver")
    do_login(other, user.username, USER_PASSWORD)
    return other


# --- ubicaciones ------------------------------------------------------------------------------------------------


def test_admin_registers_location_and_it_is_probed(location: dict[str, object], mnt: Path) -> None:
    assert location["name"] == "Expedientes"
    assert location["container_path"] == str((mnt / "expedientes").resolve())
    assert location["status"] == "ok"
    assert location["writable"] is None  # ro: no se prueba la escritura


def test_user_sees_locations_without_container_path(
    admin_client: TestClient, location: dict[str, object], user: User
) -> None:
    other = _as_user(admin_client, user)

    listed = other.get("/api/v1/locations").json()
    detail = other.get(f"/api/v1/locations/{location['id']}").json()

    assert listed["total"] == 1
    assert "container_path" not in listed["items"][0]
    assert "container_path" not in detail
    assert detail["status"] == "ok"


@pytest.mark.parametrize(
    ("method", "path"),
    [("POST", "/api/v1/locations"), ("PATCH", "/api/v1/locations/1"), ("DELETE", "/api/v1/locations/1"),
     ("POST", "/api/v1/locations/1/probe"), ("GET", "/api/v1/admin/mounts"), ("GET", "/api/v1/admin/settings"),
     ("PATCH", "/api/v1/admin/settings"), ("POST", "/api/v1/admin/capabilities/refresh")],
)  # fmt: skip
def test_admin_only_endpoints_forbidden_for_users(user_client: TestClient, method: str, path: str) -> None:
    response = user_client.request(method, path, json={})

    assert response.status_code == 403


@pytest.mark.parametrize(
    "path",
    ["/api/v1/locations", "/api/v1/locations/1", "/api/v1/fs/browse?location_id=1", "/api/v1/instance/capabilities"],
)
def test_location_endpoints_require_session(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 401


@pytest.mark.parametrize(
    ("body", "status", "fragment"),
    [
        ({**LOCATION, "name": "Otra", "path": "../fuera"}, 400, "«..»"),
        ({**LOCATION, "name": "Otra", "path": "/etc"}, 400, "relativa"),
        ({**LOCATION, "name": "Otra", "path": "no-existe"}, 400, "no existe"),
        ({**LOCATION, "name": "Otra", "path": ""}, 400, "subcarpeta"),
        ({**LOCATION, "name": "Otra", "path": "expedientes/2024"}, 400, "solapa"),
        ({**LOCATION, "name": "Otra"}, 409, "carpeta"),
        ({**LOCATION, "path": "salidas"}, 409, "nombre"),
        ({**LOCATION, "name": "expedientes", "path": "salidas"}, 409, "nombre"),
    ],
)
def test_create_location_rejects_invalid_or_duplicate(
    admin_client: TestClient, location: dict[str, object], body: dict[str, str], status: int, fragment: str
) -> None:
    response = admin_client.post("/api/v1/locations", json=body)

    assert response.status_code == status
    assert fragment in response.json()["detail"]


def test_location_cannot_contain_data_volume(admin_client: TestClient, migrated: Settings, mnt: Path) -> None:
    # Los volúmenes de la app no pueden quedar dentro de una ubicación (aquí, ``data`` bajo ``/mnt``).
    (mnt / "todo").mkdir()
    settings_with_data_inside = migrated.model_copy(update={"data_dir": mnt / "todo" / "data"})
    from app.api.deps import get_effective_settings

    admin_client.app.dependency_overrides[get_effective_settings] = lambda: settings_with_data_inside  # type: ignore[attr-defined]
    try:
        response = admin_client.post("/api/v1/locations", json={**LOCATION, "path": "todo"})
    finally:
        admin_client.app.dependency_overrides.clear()  # type: ignore[attr-defined]

    assert response.status_code == 400
    assert "volúmenes" in response.json()["detail"]


def test_update_location_keeps_container_path(admin_client: TestClient, location: dict[str, object]) -> None:
    changed = admin_client.patch(
        f"/api/v1/locations/{location['id']}", json={"name": "Expedientes NAS", "access": "rw"}
    )
    forbidden = admin_client.patch(f"/api/v1/locations/{location['id']}", json={"container_path": "/etc"})

    assert changed.status_code == 200
    assert changed.json()["name"] == "Expedientes NAS"
    assert changed.json()["writable"] is True  # al pasar a rw se vuelve a sondear con escritura
    assert changed.json()["container_path"] == location["container_path"]
    assert forbidden.status_code == 422


def test_delete_location_keeps_folder(
    admin_client: TestClient, location: dict[str, object], mnt: Path, db: Session
) -> None:
    response = admin_client.delete(f"/api/v1/locations/{location['id']}")

    assert response.status_code == 204
    assert admin_client.get(f"/api/v1/locations/{location['id']}").status_code == 404
    assert (mnt / "expedientes" / "2024").is_dir()
    actions = db.scalars(select(AuditEntry.action).where(AuditEntry.action.startswith("location."))).all()
    assert actions == ["location.create", "location.delete"]


def test_probe_marks_removed_folder_unavailable(
    admin_client: TestClient, location: dict[str, object], mnt: Path
) -> None:
    shutil.rmtree(mnt / "expedientes")

    response = admin_client.post(f"/api/v1/locations/{location['id']}/probe")

    assert response.status_code == 200
    assert (response.json()["status"], response.json()["status_reasons"]) == ("unavailable", ["missing"])


# --- explorador -------------------------------------------------------------------------------------------------


def test_browse_lists_subfolders_paginated(admin_client: TestClient, location: dict[str, object], user: User) -> None:
    other = _as_user(admin_client, user)
    root = other.get("/api/v1/fs/browse", params={"location_id": location["id"]}).json()
    page = other.get("/api/v1/fs/browse", params={"location_id": location["id"], "limit": 1, "offset": 1}).json()
    nested = other.get("/api/v1/fs/browse", params={"location_id": location["id"], "path": "2024"}).json()

    assert [(i["name"], i["path"]) for i in root["items"]] == [("2024", "2024"), ("2025", "2025")]
    assert (root["path"], root["parent"], root["total"]) == ("", None, 2)
    assert [i["name"] for i in page["items"]] == ["2025"]
    assert nested["items"] == [{"name": "enero", "path": "2024/enero"}]
    assert nested["parent"] == ""


def test_browse_escape_and_missing_give_same_404(
    admin_client: TestClient, location: dict[str, object], mnt: Path
) -> None:
    try:
        (mnt / "expedientes" / "salida").symlink_to(mnt / "salidas", target_is_directory=True)
    except OSError:
        pytest.skip("Sin permiso para crear enlaces simbólicos")
    params = {"location_id": location["id"]}

    escaped = admin_client.get("/api/v1/fs/browse", params={**params, "path": "salida"})
    missing = admin_client.get("/api/v1/fs/browse", params={**params, "path": "no-existe"})

    assert escaped.status_code == missing.status_code == 404
    # Mismo cuerpo salvo el ``request_id``: no se distingue «fuera de la ubicación» de «no existe».
    strip = lambda body: {k: v for k, v in body.items() if k != "request_id"}  # noqa: E731
    assert (
        strip(escaped.json())
        == strip(missing.json())
        == {
            "type": "about:blank",
            "title": "Carpeta no encontrada",
            "status": 404,
        }
    )


@pytest.mark.parametrize("path", ["/etc", "..", "../salidas", "C:\\Windows", "\\\\nas\\share", "a\\b"])
def test_browse_rejects_paths_outside_syntax(admin_client: TestClient, location: dict[str, object], path: str) -> None:
    response = admin_client.get("/api/v1/fs/browse", params={"location_id": location["id"], "path": path})

    assert response.status_code == 400
    assert "/" not in response.json().get("detail", "").replace("«/»", "")  # sin rutas del contenedor


def test_browse_unknown_location_is_404(admin_client: TestClient, mnt: Path) -> None:
    assert admin_client.get("/api/v1/fs/browse", params={"location_id": 99}).status_code == 404


def test_browse_unavailable_location_is_503_without_container_path(
    admin_client: TestClient, location: dict[str, object], mnt: Path
) -> None:
    shutil.rmtree(mnt / "expedientes")
    admin_client.post(f"/api/v1/locations/{location['id']}/probe")

    response = admin_client.get("/api/v1/fs/browse", params={"location_id": location["id"]})

    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")
    assert str(mnt) not in response.text


def test_mounts_lists_locations_root(admin_client: TestClient, mnt: Path) -> None:
    body = admin_client.get("/api/v1/admin/mounts").json()
    escape = admin_client.get("/api/v1/admin/mounts", params={"path": ".."})

    assert [i["name"] for i in body["items"]] == ["expedientes", "salidas"]
    assert body["location_id"] is None
    assert escape.status_code == 400


# --- ajustes ----------------------------------------------------------------------------------------------------


def test_settings_api_shows_source_and_applies_without_restart(
    admin_client: TestClient, user: User, db: Session
) -> None:
    initial = {i["key"]: i for i in admin_client.get("/api/v1/admin/settings").json()["items"]}
    updated = admin_client.patch("/api/v1/admin/settings", json={"values": {"login_max_attempts": 1}})
    other = TestClient(admin_client.app, base_url="https://testserver")
    csrf = other.get("/api/v1/auth/csrf").json()["csrf_token"]
    other.post("/api/v1/auth/login", json={"username": "ana", "password": "mal"}, headers={"X-CSRF-Token": csrf})
    locked = admin_client.get(f"/api/v1/users/{user.id}").json()

    assert initial["login_max_attempts"] == {"key": "login_max_attempts", "value": 5, "default": 5, "source": "default"}
    assert {i["key"]: i["source"] for i in updated.json()["items"]}["login_max_attempts"] == "db"
    assert locked["locked_until"] is not None  # un solo fallo ya bloquea: el ajuste vale sin reiniciar
    entry = db.scalars(select(AuditEntry).where(AuditEntry.action == "settings.update")).one()
    assert entry.details == {"changes": {"login_max_attempts": [5, 1]}}


@pytest.mark.parametrize(
    ("values", "status"), [({"password_min_length": 3}, 422), ({"app_secret_key": 1}, 400), ({"x": None}, 400)]
)
def test_settings_api_rejects_invalid(admin_client: TestClient, values: dict[str, object], status: int) -> None:
    assert admin_client.patch("/api/v1/admin/settings", json={"values": values}).status_code == status


def test_settings_api_null_restores_default(admin_client: TestClient) -> None:
    admin_client.patch("/api/v1/admin/settings", json={"values": {"password_min_length": 20}})

    body = admin_client.patch("/api/v1/admin/settings", json={"values": {"password_min_length": None}}).json()

    assert {i["key"]: (i["value"], i["source"]) for i in body["items"]}["password_min_length"] == (12, "default")


# --- capacidades y salud ----------------------------------------------------------------------------------------


@pytest.fixture
def fake_capabilities(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    """Sustituye el subproceso: la caché devuelve un resultado fijo y anota los refrescos pedidos."""
    calls: list[str] = []
    snapshot = CapabilitiesSnapshot(
        status="ok",
        checked_at=datetime(2026, 10, 31, tzinfo=UTC),
        capabilities=Capabilities(
            gpu_support_installed=True,
            gpu_active=False,
            asr_installed=False,
            ffmpeg_installed=True,
            av_ready=False,
            libreoffice_installed=False,
        ),
    )
    monkeypatch.setattr(capabilities_cache, "get", lambda: snapshot)
    monkeypatch.setattr(capabilities_cache, "refresh", lambda: calls.append("refresh") or True)
    yield calls


def test_capabilities_for_any_session(user_client: TestClient, fake_capabilities: list[str]) -> None:
    body = user_client.get("/api/v1/instance/capabilities").json()

    assert body["status"] == "ok"
    assert body["capabilities"]["gpu_active"] is False
    assert body["capabilities"]["ffmpeg_installed"] is True
    assert body["doc_organize_version"] == "0.9.3"


def test_admin_refreshes_capabilities(admin_client: TestClient, fake_capabilities: list[str]) -> None:
    response = admin_client.post("/api/v1/admin/capabilities/refresh")

    assert response.status_code == 202
    assert fake_capabilities == ["refresh"]


def test_health_reports_worst_location_status(admin_client: TestClient, location: dict[str, object], mnt: Path) -> None:
    assert admin_client.get("/api/health").json()["locations"] == "ok"

    shutil.rmtree(mnt / "expedientes")
    admin_client.post(f"/api/v1/locations/{location['id']}/probe")

    body = admin_client.get("/api/health").json()
    assert (body["status"], body["locations"]) == ("ok", "unavailable")


def test_health_without_locations(client: TestClient) -> None:
    assert client.get("/api/health").json()["locations"] == "none"
