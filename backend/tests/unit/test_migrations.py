"""Migraciones de Alembic desde la línea base ``0033`` de la 3.0 (ADR-018): sube, baja y rechaza BD anteriores a 2.7."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import CheckConstraint, inspect

from app.core.config import Settings
from app.db.base import Base
from app.db.migrations import UnsupportedRevisionError
from app.db.session import get_engine
from tests import schema_snapshot

BACKEND_DIR = Path(__file__).resolve().parents[2]
BASELINE = "0033"


def _config() -> Config:
    return Config(str(BACKEND_DIR / "alembic.ini"))


def test_single_head() -> None:
    assert len(ScriptDirectory.from_config(_config()).get_heads()) == 1


def test_the_chain_starts_at_the_0033_baseline() -> None:
    """La línea base conserva el id ``0033``: una BD de la 2.7.x o la 2.8.x ya está en ella."""
    script = ScriptDirectory.from_config(_config())
    (base,) = script.get_bases()
    assert base == BASELINE
    assert script.get_revision(BASELINE).down_revision is None


def test_0033_matches_the_schema_snapshot(settings: Settings) -> None:
    """La BD en ``0033`` es exactamente ``tests/fixtures/schema_0033.sql``, la que dejaba la cadena ``0001→0033``."""
    command.upgrade(_config(), schema_snapshot.REVISION)
    get_engine().dispose()

    assert schema_snapshot.dump(settings.data_dir / "config.db") == schema_snapshot.SNAPSHOT.read_text(encoding="utf-8")


def test_upgrade_and_downgrade(settings: Settings) -> None:
    config = _config()

    command.upgrade(config, "head")
    assert "alembic_version" in inspect(get_engine()).get_table_names()

    command.downgrade(config, "base")
    with get_engine().connect() as conn:
        assert conn.exec_driver_sql("SELECT count(*) FROM alembic_version").scalar() == 0
    assert set(inspect(get_engine()).get_table_names()) == {"alembic_version"}

    command.upgrade(config, "head")
    assert "users" in inspect(get_engine()).get_table_names()


def test_a_2_8_database_is_already_at_the_baseline(settings: Settings) -> None:
    """Una ``config.db`` en ``0033`` (la de la 2.7.x/2.8.x) no ejecuta nada al subir a la línea base."""
    config = _config()
    command.upgrade(config, BASELINE)
    with get_engine().begin() as conn:
        conn.exec_driver_sql("UPDATE tenants SET name = 'Mi organización' WHERE id = 1")

    command.upgrade(config, BASELINE)

    with get_engine().connect() as conn:
        assert conn.exec_driver_sql("SELECT name FROM tenants WHERE id = 1").scalar() == "Mi organización"


def test_a_database_older_than_2_7_is_rejected_without_its_path(settings: Settings) -> None:
    config = _config()
    command.upgrade(config, "head")
    with get_engine().begin() as conn:
        conn.exec_driver_sql("UPDATE alembic_version SET version_num = '0029'")

    with pytest.raises(UnsupportedRevisionError) as caught:
        command.upgrade(config, "head")

    message = str(caught.value)
    assert "0029" in message and "2.8.x" in message
    assert str(settings.data_dir) not in message and "config.db" not in message


def test_projects_schema_matches_the_model(settings: Settings) -> None:
    """Sin test de deriva general: al menos ``projects`` (nulabilidad de las ubicaciones y CHECK de 2.3.1)."""
    command.upgrade(_config(), "head")
    engine = get_engine()
    columns = {c["name"]: c["nullable"] for c in inspect(engine).get_columns("projects")}
    model = Base.metadata.tables["projects"]
    for name in ("source_location_id", "destination_location_id"):
        assert columns[name] is model.c[name].nullable is True
    checks = {c["name"] for c in inspect(engine).get_check_constraints("projects")}
    expected = {c.name for c in model.constraints if isinstance(c, CheckConstraint)}
    assert expected <= checks
    assert "ck_projects_locations" in checks


def test_roundtrip_script_on_a_baseline_copy(settings: Settings, tmp_path: Path) -> None:
    """``scripts/migration_roundtrip.py`` sobre una copia en la línea base: sube, baja y deja las mismas filas."""
    command.upgrade(_config(), "head")
    get_engine().dispose()
    copy = tmp_path / "copia" / "config.db"
    copy.parent.mkdir()
    shutil.copy(settings.data_dir / "config.db", copy)

    result = subprocess.run(  # noqa: S603 - el script del propio repositorio
        [sys.executable, str(BACKEND_DIR / "scripts" / "migration_roundtrip.py"), str(copy)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env={**{k: v for k, v in os.environ.items() if k != "DOW_DATA_DIR"}, "PYTHONIOENCODING": "utf-8"},
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert f"Revisión de partida: {BASELINE}" in result.stdout
