from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import __version__
from app.api import health


def test_health_ok(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["version"] == __version__
    assert body["doc_organize_version"] == "0.10.0"


def test_health_degraded_without_database(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health, "ping", lambda _engine: False)

    response = client.get("/api/health")

    assert response.status_code == 503
    assert response.json() | {"version": None} == {
        "status": "degraded",
        "version": None,
        "doc_organize_version": "0.10.0",
        "database": "error",
        "locations": "unknown",
    }


def test_health_degraded_without_library(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health, "library_version", lambda: None)

    response = client.get("/api/health")

    assert response.status_code == 503
    assert response.json()["doc_organize_version"] is None
