"""Comportamiento HTTP común: *problem details*, ``X-Request-ID``, cabeceras de seguridad y documentación."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.config import Settings
from app.core.middleware import API_CSP
from app.main import create_app


def test_unknown_api_route_is_problem_json(client: TestClient) -> None:
    response = client.get("/api/v1/no-existe")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["status"] == 404
    assert body["request_id"] == response.headers["X-Request-ID"]


class Payload(BaseModel):
    name: str


def test_validation_error_is_problem_json(settings: Settings) -> None:
    app = create_app(settings)

    @app.post("/api/v1/_echo")
    def echo(payload: Payload) -> Payload:
        return payload

    response = TestClient(app).post("/api/v1/_echo", json={})

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["errors"][0]["loc"] == ["body", "name"]


def test_unexpected_error_hides_detail(settings: Settings) -> None:
    app = create_app(settings)

    @app.get("/api/v1/_boom")
    def boom() -> None:
        raise RuntimeError("/mnt/origen/secreto.pdf no se pudo abrir")

    response = TestClient(app, raise_server_exceptions=False).get("/api/v1/_boom")

    assert response.status_code == 500
    assert "secreto" not in response.text
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["title"] == "Error interno"
    assert response.json()["request_id"] == response.headers["X-Request-ID"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_request_id_is_generated(client: TestClient) -> None:
    response = client.get("/api/health")

    assert len(response.headers["X-Request-ID"]) == 32


@pytest.mark.parametrize(("incoming", "kept"), [("proxy-abc-123", True), ("mal id\n<script>", False), ("x", False)])
def test_request_id_from_client_only_if_safe(client: TestClient, incoming: str, kept: bool) -> None:
    response = client.get("/api/health", headers={"X-Request-ID": incoming})

    assert (response.headers["X-Request-ID"] == incoming) is kept


def test_security_headers(client: TestClient) -> None:
    headers = client.get("/api/health").headers

    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["Referrer-Policy"] == "same-origin"
    assert headers["Content-Security-Policy"] == API_CSP


@pytest.mark.parametrize(("environment", "docs", "schema"), [("development", 200, 200), ("test", 404, 200)])
def test_docs_only_in_development(settings: Settings, environment: str, docs: int, schema: int) -> None:
    client = TestClient(create_app(settings.model_copy(update={"environment": environment})))

    assert client.get("/api/docs").status_code == docs
    assert client.get("/api/openapi.json").status_code == schema


def test_no_openapi_in_production(settings: Settings) -> None:
    prod = settings.model_copy(update={"environment": "production", "app_secret_key": "k", "fernet_keys": "f"})

    assert TestClient(create_app(prod)).get("/api/openapi.json").status_code == 404
