from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.db.session import SQLITE_PRAGMAS, build_engine


def test_database_url_points_to_config_db(tmp_path: Path) -> None:
    settings = Settings(environment="test", data_dir=tmp_path)

    assert settings.database_url == f"sqlite:///{(tmp_path / 'config.db').as_posix()}"


def test_defaults_are_container_paths() -> None:
    settings = Settings(environment="test")

    assert (settings.data_dir, settings.locations_root) == (Path("/data"), Path("/mnt"))


def test_secrets_are_not_rendered() -> None:
    settings = Settings(environment="test", app_secret_key="muy-secreta")  # type: ignore[arg-type]

    assert "muy-secreta" not in repr(settings)


def test_secrets_read_from_docker_secrets_dir(tmp_path: Path) -> None:
    (tmp_path / "dow_app_secret_key").write_text("desde-secret", encoding="utf-8")
    (tmp_path / "dow_fernet_keys").write_text("clave-fernet", encoding="utf-8")

    settings = Settings(environment="production", _secrets_dir=tmp_path)  # type: ignore[call-arg]

    assert settings.app_secret_key is not None
    assert settings.app_secret_key.get_secret_value() == "desde-secret"


def test_production_requires_secrets(tmp_path: Path) -> None:
    (tmp_path / "dow_app_secret_key").write_text("solo-una", encoding="utf-8")

    with pytest.raises(ValidationError, match="dow_fernet_keys"):
        Settings(environment="production", _secrets_dir=tmp_path)  # type: ignore[call-arg]


def test_sqlite_pragmas_applied(tmp_path: Path) -> None:
    engine = build_engine(f"sqlite:///{(tmp_path / 'c.db').as_posix()}")
    with engine.connect() as conn:
        journal = conn.exec_driver_sql("PRAGMA journal_mode").scalar()
        fks = conn.exec_driver_sql("PRAGMA foreign_keys").scalar()
        busy = conn.exec_driver_sql("PRAGMA busy_timeout").scalar()
    engine.dispose()

    assert len(SQLITE_PRAGMAS) == 4
    assert (journal, fks, busy) == ("wal", 1, 5000)
