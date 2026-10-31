from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def spa_client(settings: Settings) -> TestClient:
    static = settings.static_dir
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<!doctype html><title>spa</title>", encoding="utf-8")
    (static / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (static.parent / "secreto.txt").write_text("no", encoding="utf-8")
    return TestClient(create_app(settings))


def test_client_route_falls_back_to_index(spa_client: TestClient) -> None:
    response = spa_client.get("/proyectos/42")

    assert response.status_code == 200
    assert "<title>spa</title>" in response.text


def test_assets_are_served(spa_client: TestClient) -> None:
    assert spa_client.get("/assets/app.js").text == "console.log(1)"


def test_api_routes_do_not_fall_back(spa_client: TestClient) -> None:
    assert spa_client.get("/api/v1/x").status_code == 404


def test_path_traversal_returns_index(spa_client: TestClient, settings: Settings) -> None:
    response = spa_client.get("/..%2Fsecreto.txt")

    assert response.text != "no"
    assert Path(settings.static_dir.parent / "secreto.txt").exists()


def test_spa_has_its_own_csp(spa_client: TestClient) -> None:
    csp = spa_client.get("/").headers["Content-Security-Policy"]

    assert "script-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
