"""Fixtures comunes: ajustes aislados en ``tmp_path`` y cliente HTTP sobre la app."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.db.session import get_engine
from app.main import create_app


@pytest.fixture
def settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Settings]:
    """Ajustes con carpetas temporales; limpia las cachés de proceso."""
    monkeypatch.setenv("DOW_ENVIRONMENT", "test")
    for name in ("data", "workspace", "static"):
        monkeypatch.setenv(f"DOW_{name.upper()}_DIR", str(tmp_path / name))
    monkeypatch.setenv("DOW_LOCATIONS_ROOT", str(tmp_path / "mnt"))
    get_settings.cache_clear()
    get_engine.cache_clear()
    yield get_settings()
    get_engine().dispose()
    get_settings.cache_clear()
    get_engine.cache_clear()


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client
