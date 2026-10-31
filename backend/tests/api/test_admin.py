"""Administración de usuarios, sesiones y auditoría: permisos, 404, 409 y efectos."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEntry, User
from tests.conftest import USER_PASSWORD, do_login

ADMIN_ENDPOINTS = [
    ("GET", "/api/v1/users"),
    ("POST", "/api/v1/users"),
    ("GET", "/api/v1/users/1"),
    ("PATCH", "/api/v1/users/1"),
    ("GET", "/api/v1/audit"),
]
# Las sesiones exigen sesión, pero no rol admin: un usuario ve y cierra las suyas.
SESSION_ENDPOINTS = [("GET", "/api/v1/sessions"), ("DELETE", "/api/v1/sessions/1")]
NEW_USER = {"username": "Luis", "display_name": "Luis Pérez", "password": "luis-frase-de-paso", "role": "user"}


def _other_client(client: TestClient) -> TestClient:
    return TestClient(client.app, base_url="https://testserver")


@pytest.mark.parametrize(("method", "path"), ADMIN_ENDPOINTS + SESSION_ENDPOINTS)
def test_admin_endpoints_require_session(client: TestClient, method: str, path: str) -> None:
    csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]

    response = client.request(method, path, json=NEW_USER, headers={"X-CSRF-Token": csrf})

    assert response.status_code == 401


@pytest.mark.parametrize(("method", "path"), ADMIN_ENDPOINTS)
def test_admin_endpoints_forbidden_for_role_user(user_client: TestClient, method: str, path: str) -> None:
    response = user_client.request(method, path, json=NEW_USER)

    assert response.status_code == 403


def test_create_list_and_get_user(admin_client: TestClient, db: Session) -> None:
    created = admin_client.post("/api/v1/users", json=NEW_USER)

    assert created.status_code == 201
    body = created.json()
    assert body["username"] == "luis"
    assert "password" not in body and "password_hash" not in body
    listed = admin_client.get("/api/v1/users", params={"q": "pér"}).json()
    assert [u["username"] for u in listed["items"]] == ["luis"]
    assert admin_client.get(f"/api/v1/users/{body['id']}").json()["display_name"] == "Luis Pérez"
    assert db.scalars(select(AuditEntry.action).where(AuditEntry.action == "user.create")).all()


def test_create_user_conflict_and_validation(admin_client: TestClient) -> None:
    admin_client.post("/api/v1/users", json=NEW_USER)

    assert admin_client.post("/api/v1/users", json={**NEW_USER, "username": "LUIS"}).status_code == 409
    assert admin_client.post("/api/v1/users", json={**NEW_USER, "username": "a b"}).status_code == 422
    assert admin_client.post("/api/v1/users", json={**NEW_USER, "role": "root"}).status_code == 422
    weak = admin_client.post("/api/v1/users", json={**NEW_USER, "username": "x1y", "password": "corta"})
    assert weak.status_code == 400


def test_unknown_user_is_404(admin_client: TestClient) -> None:
    assert admin_client.get("/api/v1/users/9999").status_code == 404
    assert admin_client.patch("/api/v1/users/9999", json={"role": "admin"}).status_code == 404


def test_deactivate_revokes_sessions_and_reactivate_allows_login(admin_client: TestClient, user: User) -> None:
    ana = _other_client(admin_client)
    do_login(ana, "ana", USER_PASSWORD)

    response = admin_client.patch(f"/api/v1/users/{user.id}", json={"is_active": False})

    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert ana.get("/api/v1/auth/me").status_code == 401
    admin_client.patch(f"/api/v1/users/{user.id}", json={"is_active": True})
    do_login(ana, "ana", USER_PASSWORD)


def test_admin_password_reset_revokes_sessions(admin_client: TestClient, user: User) -> None:
    ana = _other_client(admin_client)
    do_login(ana, "ana", USER_PASSWORD)

    response = admin_client.patch(f"/api/v1/users/{user.id}", json={"password": "restablecida-1234"})

    assert response.status_code == 200
    assert ana.get("/api/v1/auth/me").status_code == 401
    do_login(ana, "ana", "restablecida-1234")


def test_admin_cannot_demote_or_deactivate_self(admin_client: TestClient, admin: User) -> None:
    assert admin_client.patch(f"/api/v1/users/{admin.id}", json={"role": "user"}).status_code == 409
    assert admin_client.patch(f"/api/v1/users/{admin.id}", json={"is_active": False}).status_code == 409


def test_promote_user_to_admin_is_audited(admin_client: TestClient, user: User, db: Session) -> None:
    response = admin_client.patch(f"/api/v1/users/{user.id}", json={"role": "admin", "display_name": "Ana G."})

    assert response.json()["role"] == "admin"
    entry = db.scalars(select(AuditEntry).where(AuditEntry.action == "user.update")).one()
    assert entry.details == {"fields": ["display_name", "role"], "role": "admin"}


def test_list_and_revoke_sessions(admin_client: TestClient, user: User) -> None:
    ana = _other_client(admin_client)
    do_login(ana, "ana", USER_PASSWORD)

    page = admin_client.get("/api/v1/sessions").json()
    assert page["total"] == 2
    assert {s["username"] for s in page["items"]} == {"admin", "ana"}
    assert [s["current"] for s in page["items"] if s["username"] == "admin"] == [True]
    assert all("token" not in key for s in page["items"] for key in s)
    ana_session = next(s for s in page["items"] if s["username"] == "ana")

    assert admin_client.delete(f"/api/v1/sessions/{ana_session['id']}").status_code == 204
    assert ana.get("/api/v1/auth/me").status_code == 401
    assert admin_client.delete(f"/api/v1/sessions/{ana_session['id']}").status_code == 404
    assert admin_client.get("/api/v1/sessions", params={"user_id": user.id}).json()["total"] == 0


def test_audit_lists_newest_first_and_filters(admin_client: TestClient) -> None:
    admin_client.post("/api/v1/users", json=NEW_USER)

    page = admin_client.get("/api/v1/audit").json()
    assert page["items"][0]["action"] == "user.create"
    assert page["items"][0]["actor_username"] == "admin"
    filtered = admin_client.get("/api/v1/audit", params={"action": "auth."}).json()
    assert {e["action"] for e in filtered["items"]} == {"auth.login"}
    assert admin_client.get("/api/v1/audit", params={"limit": 500}).status_code == 422


def test_user_sees_and_revokes_only_own_sessions(
    client: TestClient, admin: User, user: User, make_user: Callable[..., User]
) -> None:
    other = make_user("berta")
    do_login(client, user.username, USER_PASSWORD)
    berta = _other_client(client)
    do_login(berta, other.username, USER_PASSWORD)
    berta_session = berta.get("/api/v1/sessions").json()["items"][0]["id"]

    own = client.get("/api/v1/sessions", params={"user_id": other.id}).json()
    revoke_other = client.delete(f"/api/v1/sessions/{berta_session}")

    assert [s["username"] for s in own["items"]] == ["ana"]
    assert own["items"][0]["current"] is True
    assert revoke_other.status_code == 404
    assert berta.get("/api/v1/auth/me").status_code == 200
    assert client.delete(f"/api/v1/sessions/{own['items'][0]['id']}").status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401


def test_admin_unlocks_user_after_lockout(admin_client: TestClient, user: User, db: Session) -> None:
    other = _other_client(admin_client)
    csrf = other.get("/api/v1/auth/csrf").json()["csrf_token"]
    for _ in range(5):
        other.post("/api/v1/auth/login", json={"username": "ana", "password": "mal"}, headers={"X-CSRF-Token": csrf})
    locked = admin_client.get(f"/api/v1/users/{user.id}").json()

    unlocked = admin_client.patch(f"/api/v1/users/{user.id}", json={"unlock": True})

    assert locked["locked_until"] is not None
    assert unlocked.status_code == 200
    assert unlocked.json()["locked_until"] is None
    assert unlocked.json()["failed_attempts"] == 0
    do_login(other, "ana", USER_PASSWORD)
    actions = db.scalars(select(AuditEntry.action).where(AuditEntry.action == "user.unlock")).all()
    assert actions == ["user.unlock"]


def test_create_user_rejects_common_password(admin_client: TestClient) -> None:
    response = admin_client.post("/api/v1/users", json={**NEW_USER, "password": "Password1234!"})

    assert response.status_code == 400
    assert "común" in response.json()["detail"]


def test_audit_filters_by_actor_and_date_range(admin_client: TestClient, user: User) -> None:
    admin_client.post("/api/v1/users", json=NEW_USER)

    by_actor = admin_client.get("/api/v1/audit", params={"actor": "ADMIN", "action": "user."}).json()
    future = admin_client.get("/api/v1/audit", params={"since": "2999-01-01T00:00:00Z"}).json()
    past = admin_client.get("/api/v1/audit", params={"until": "2000-01-01T00:00:00+00:00"}).json()

    assert [e["action"] for e in by_actor["items"]] == ["user.create"]
    assert by_actor["items"][0]["actor_username"] == "admin"
    assert future["total"] == 0
    assert past["total"] == 0


def test_audit_rejects_dates_without_timezone(admin_client: TestClient) -> None:
    response = admin_client.get("/api/v1/audit", params={"since": "2026-10-31T10:00:00"})

    assert response.status_code == 422
