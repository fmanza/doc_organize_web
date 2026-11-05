"""Fase 10: límite de peticiones por IP (429 con ``Retry-After``) y ``/metrics`` con token (404 sin él)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.ratelimit import SlidingWindow
from app.db.models import User
from app.main import create_app
from tests.conftest import ADMIN_PASSWORD, do_login

TOKEN = "metrics-token-de-prueba-0123456789"


def _client(monkeypatch: pytest.MonkeyPatch, **env: str) -> TestClient:
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    return TestClient(create_app(get_settings()), base_url="https://testserver")


@pytest.fixture
def limited(migrated: Settings, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    with _client(monkeypatch, DOW_RATE_LIMIT_LOGIN="3", DOW_RATE_LIMIT_WRITE="5") as client:
        yield client


def test_sliding_window_frees_slots_as_time_passes() -> None:
    now = [0.0]
    window = SlidingWindow(2, window=60, clock=lambda: now[0])

    assert window.hit("ip") == 0 and window.hit("ip") == 0
    assert window.hit("ip") == 60
    assert window.hit("otra") == 0  # cada IP lleva su cuenta
    now[0] = 30.0
    assert window.hit("ip") == 30
    now[0] = 60.5
    assert window.hit("ip") == 0


def test_too_many_logins_from_one_ip_get_429(limited: TestClient, admin: User) -> None:
    csrf = {"X-CSRF-Token": limited.get("/api/v1/auth/csrf").json()["csrf_token"]}
    for _ in range(3):
        response = limited.post("/api/v1/auth/login", json={"username": "nadie", "password": "x" * 12}, headers=csrf)
        assert response.status_code == 401

    response = limited.post(
        "/api/v1/auth/login", json={"username": admin.username, "password": ADMIN_PASSWORD}, headers=csrf
    )

    assert response.status_code == 429
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "rate_limited" and int(response.headers["Retry-After"]) >= 1
    assert response.headers["X-Request-ID"] and response.headers["X-Content-Type-Options"] == "nosniff"


def test_writes_are_limited_but_reads_are_not(limited: TestClient, admin: User) -> None:
    do_login(limited, admin.username, ADMIN_PASSWORD)  # el inicio de sesión cuenta en su propio cubo
    statuses = [limited.post("/api/v1/auth/logout").status_code for _ in range(6)]

    assert 429 not in statuses[:5] and statuses[5] == 429
    assert limited.get("/api/health").status_code == 200


def test_metrics_do_not_exist_without_token(client: TestClient) -> None:
    assert client.get("/metrics").status_code == 404


def test_metrics_need_the_right_token(migrated: Settings, monkeypatch: pytest.MonkeyPatch, admin: User) -> None:
    with _client(monkeypatch, DOW_METRICS_TOKEN=TOKEN) as client:
        assert client.get("/metrics").status_code == 404
        assert client.get("/metrics", headers={"Authorization": "Bearer otro"}).status_code == 404
        do_login(client, admin.username, ADMIN_PASSWORD)
        client.get("/api/v1/projects/12345")

        response = client.get("/metrics", headers={"Authorization": f"Bearer {TOKEN}"})

    assert response.status_code == 200 and response.headers["content-type"].startswith("text/plain; version=0.0.4")
    body = response.text
    assert 'route="/api/v1/projects/{project_id}"' in body and "12345" not in body
    assert 'dow_http_requests_total{method="POST",route="/api/v1/auth/login",status="200"} 1' in body
    assert "dow_build_info{" in body and "dow_workers_alive 0" in body and "dow_database_bytes " in body
    assert admin.username not in body


def test_api_responses_are_not_cached_and_carry_hsts(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.headers["Cache-Control"] == "no-store"
    # Fuera de development las cookies son Secure: HTTPS en el proxy, y el navegador debe recordarlo.
    assert response.headers["Strict-Transport-Security"].startswith("max-age=31536000")


def test_a_body_over_the_limit_is_rejected_before_reading_it(
    migrated: Settings, monkeypatch: pytest.MonkeyPatch, admin: User
) -> None:
    with _client(monkeypatch, DOW_MAX_REQUEST_MB="1") as client:
        do_login(client, admin.username, ADMIN_PASSWORD)
        big = b'{"name": "' + b"x" * (1024 * 1024) + b'"}'

        response = client.post("/api/v1/tenants", content=big, headers={"Content-Type": "application/json"})

        def chunks() -> Iterator[bytes]:
            yield big[: len(big) // 2]
            yield big[len(big) // 2 :]

        chunked = client.post("/api/v1/tenants", content=chunks(), headers={"Content-Type": "application/json"})

    assert response.status_code == 413 and response.json()["code"] == "body_too_large"
    assert chunked.status_code == 411 and chunked.json()["code"] == "length_required"
