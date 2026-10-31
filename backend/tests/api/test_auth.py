from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEntry, User, UserSession
from tests.conftest import USER_PASSWORD, do_login


def _csrf(client: TestClient) -> str:
    token: str = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    return token


def _login(client: TestClient, username: str, password: str) -> int:
    response = client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}, headers={"X-CSRF-Token": _csrf(client)}
    )
    return response.status_code


def test_login_sets_session_and_csrf_cookies_with_flags(client: TestClient, user: User) -> None:
    csrf = _csrf(client)
    response = client.post(
        "/api/v1/auth/login", json={"username": "ana", "password": USER_PASSWORD}, headers={"X-CSRF-Token": csrf}
    )

    assert response.status_code == 200
    assert response.json() == {"id": user.id, "username": "ana", "display_name": "Ana", "role": "user"}
    cookies = response.headers.get_list("set-cookie")
    session_cookie = next(c for c in cookies if c.startswith("__Host-dow_session=")).lower()
    csrf_cookie = next(c for c in cookies if c.startswith("__Host-dow_csrf=")).lower()
    for flag in ("httponly", "secure", "samesite=lax", "path=/"):
        assert flag in session_cookie
    assert "secure" in csrf_cookie
    assert "httponly" not in csrf_cookie


def test_me_requires_session(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")


def test_me_returns_current_user(user_client: TestClient) -> None:
    assert user_client.get("/api/v1/auth/me").json()["username"] == "ana"


@pytest.mark.parametrize("username", ["ana", "nadie"])
def test_bad_credentials_give_same_generic_401(client: TestClient, user: User, username: str) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "no-es-la-buena"},
        headers={"X-CSRF-Token": _csrf(client)},
    )

    assert response.status_code == 401
    assert response.json()["title"] == "Credenciales no válidas"
    assert "__Host-dow_session" not in client.cookies


def test_inactive_user_cannot_login(client: TestClient, user: User, db: Session) -> None:
    user.is_active = False
    db.commit()

    assert _login(client, "ana", USER_PASSWORD) == 401


def test_login_without_csrf_is_forbidden(client: TestClient, user: User) -> None:
    client.get("/api/v1/auth/csrf")

    response = client.post("/api/v1/auth/login", json={"username": "ana", "password": USER_PASSWORD})

    assert response.status_code == 403


def test_csrf_header_must_match_cookie(client: TestClient, user: User) -> None:
    client.get("/api/v1/auth/csrf")

    response = client.post(
        "/api/v1/auth/login", json={"username": "ana", "password": USER_PASSWORD}, headers={"X-CSRF-Token": "otro"}
    )

    assert response.status_code == 403


def test_injected_csrf_cookie_is_rejected_with_session(user_client: TestClient) -> None:
    # Fijar cookie y cabecera al mismo valor no basta: con sesión se exige HMAC(clave, token_de_sesión).
    user_client.cookies.delete("__Host-dow_csrf")
    user_client.cookies.set("__Host-dow_csrf", "inyectado")

    response = user_client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": "inyectado"})

    assert response.status_code == 403


def test_csrf_endpoint_returns_session_bound_token_when_logged_in(user_client: TestClient) -> None:
    assert _csrf(user_client) == user_client.headers["X-CSRF-Token"]


def test_login_rotates_previous_session(client: TestClient, user: User, db: Session) -> None:
    do_login(client, "ana", USER_PASSWORD)
    first = client.cookies["__Host-dow_session"]
    do_login(client, "ana", USER_PASSWORD)

    assert client.cookies["__Host-dow_session"] != first
    assert len(db.scalars(select(UserSession).where(UserSession.user_id == user.id)).all()) == 1


def test_session_token_is_not_stored_in_clear(user_client: TestClient, db: Session) -> None:
    token = user_client.cookies["__Host-dow_session"]

    assert token not in db.scalars(select(UserSession.token_hash)).all()


def test_logout_deletes_session_and_cookies(user_client: TestClient, db: Session) -> None:
    response = user_client.post("/api/v1/auth/logout")

    assert response.status_code == 204
    assert db.scalars(select(UserSession)).all() == []
    assert user_client.get("/api/v1/auth/me").status_code == 401


def test_logout_requires_session(client: TestClient) -> None:
    assert client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": _csrf(client)}).status_code == 401


def test_change_password_revokes_other_sessions(client: TestClient, user: User) -> None:
    other = TestClient(client.app, base_url="https://testserver")
    do_login(other, "ana", USER_PASSWORD)
    do_login(client, "ana", USER_PASSWORD)

    response = client.post(
        "/api/v1/auth/password",
        json={"current_password": USER_PASSWORD, "new_password": "nueva-frase-de-paso"},
    )

    assert response.status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 200
    assert other.get("/api/v1/auth/me").status_code == 401
    assert _login(other, "ana", "nueva-frase-de-paso") == 200


def test_change_password_rejects_wrong_current_and_weak_new(user_client: TestClient) -> None:
    wrong = user_client.post(
        "/api/v1/auth/password", json={"current_password": "no-es", "new_password": "nueva-frase-de-paso"}
    )
    weak = user_client.post("/api/v1/auth/password", json={"current_password": USER_PASSWORD, "new_password": "corta"})

    assert wrong.status_code == 400
    assert weak.status_code == 400
    assert "al menos" in weak.json()["detail"]


def test_password_change_requires_session(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/password",
        json={"current_password": "a", "new_password": "b"},
        headers={"X-CSRF-Token": _csrf(client)},
    )

    assert response.status_code == 401


def test_login_validation_error_does_not_echo_password(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "", "password": "secreto-visible"},
        headers={"X-CSRF-Token": _csrf(client)},
    )

    assert response.status_code == 422
    assert "secreto-visible" not in response.text


def test_passwords_never_logged_nor_audited(
    client: TestClient, user: User, db: Session, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    _login(client, "ana", "clave-erronea-xyz")
    do_login(client, "ana", USER_PASSWORD)

    assert "Inicio de sesión rechazado" in caplog.text
    assert "clave-erronea-xyz" not in caplog.text
    assert USER_PASSWORD not in caplog.text
    assert client.cookies["__Host-dow_session"] not in caplog.text
    details = " ".join(str(e.details) for e in db.scalars(select(AuditEntry)).all())
    assert "clave-erronea-xyz" not in details
    assert USER_PASSWORD not in details


def test_login_success_and_failure_are_audited(client: TestClient, user: User, db: Session) -> None:
    _login(client, "nadie", "lo-que-sea")
    do_login(client, "ana", USER_PASSWORD)

    entries = db.scalars(select(AuditEntry).where(AuditEntry.action == "auth.login").order_by(AuditEntry.id)).all()
    assert [(e.outcome, e.actor_user_id) for e in entries] == [("failure", None), ("success", user.id)]
    # Sin el nombre probado: un usuario inexistente puede ser una contraseña tecleada en el campo equivocado.
    assert entries[0].details == {"reason": "unknown_user"}


def test_health_stays_public(client: TestClient) -> None:
    assert client.get("/api/health").status_code == 200
