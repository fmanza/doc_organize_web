"""La cadena de Alembic sube y baja entera (portabilidad, D8)."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from app.core.config import Settings
from app.db.session import get_engine

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _config() -> Config:
    return Config(str(BACKEND_DIR / "alembic.ini"))


def test_single_head() -> None:
    assert len(ScriptDirectory.from_config(_config()).get_heads()) == 1


def test_upgrade_and_downgrade(settings: Settings) -> None:
    config = _config()

    command.upgrade(config, "head")
    assert "alembic_version" in inspect(get_engine()).get_table_names()

    command.downgrade(config, "base")
    with get_engine().connect() as conn:
        assert conn.exec_driver_sql("SELECT count(*) FROM alembic_version").scalar() == 0


def test_0009_keeps_users_sessions_and_audit(settings: Settings) -> None:
    """Recrear ``users`` (SQLite) no dispara los ``ON DELETE`` de sus hijas: ``env.py`` desactiva las claves."""
    config = _config()
    command.upgrade(config, "0008")
    engine = get_engine()
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO users (tenant_id, username, display_name, password_hash, role, is_active, failed_attempts,"
            " password_changed_at, created_at, updated_at) VALUES"
            " (1, 'ana', 'Ana', 'x', 'admin', 1, 0, '2026-01-01', '2026-01-01', '2026-01-01'),"
            " (1, 'luis', 'Luis', 'x', 'user', 1, 0, '2026-01-01', '2026-01-01', '2026-01-01')"
        )
        conn.exec_driver_sql(
            "INSERT INTO sessions (token_hash, user_id, created_at, last_seen_at, expires_at)"
            " VALUES ('h', 2, '2026-01-01', '2026-01-01', '2027-01-01')"
        )
        conn.exec_driver_sql(
            "INSERT INTO audit_log (tenant_id, ts, actor_user_id, action, outcome) VALUES (1, '2026-01-01', 1, 'x', 'ok')"
        )

    command.upgrade(config, "0009")

    with engine.connect() as conn:
        rows = conn.exec_driver_sql(
            "SELECT u.username, u.is_instance_admin, r.builtin FROM users u JOIN roles r ON r.id = u.role_id"
            " ORDER BY u.username"
        ).all()
        assert [tuple(r) for r in rows] == [("ana", 1, "admin"), ("luis", 0, "user")]
        assert conn.exec_driver_sql("SELECT count(*) FROM sessions").scalar() == 1
        assert conn.exec_driver_sql("SELECT actor_user_id FROM audit_log").scalar() == 1
        assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1

    command.downgrade(config, "0008")

    with engine.connect() as conn:
        roles = conn.exec_driver_sql("SELECT username, role FROM users ORDER BY username").all()
        assert [tuple(r) for r in roles] == [("ana", "admin"), ("luis", "user")]
        assert conn.exec_driver_sql("SELECT count(*) FROM sessions").scalar() == 1


def test_0011_adds_empty_exclusions_and_drops_them(settings: Settings) -> None:
    """web 1.4.0: columnas JSON con ``[]`` para las filas existentes; bajar las quita sin tocar el resto."""
    config = _config()
    command.upgrade(config, "0010")
    engine = get_engine()
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO locations (tenant_id, name, container_path, kind, usage, access, visibility, status,"
            " created_at, updated_at) VALUES (1, 'Origen', '/mnt/origen', 'local', 'source', 'ro', 'global',"
            " 'ok', '2026-01-01', '2026-01-01')"
        )

    command.upgrade(config, "0011")

    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT ignore_patterns FROM locations").scalar() == "[]"
    assert "excluded_subpaths" in {c["name"] for c in inspect(engine).get_columns("scanned_folders")}

    command.downgrade(config, "0010")

    assert "ignore_patterns" not in {c["name"] for c in inspect(get_engine()).get_columns("locations")}
    assert "excluded_subpaths" not in {c["name"] for c in inspect(get_engine()).get_columns("scanned_folders")}
    with get_engine().connect() as conn:
        assert conn.exec_driver_sql("SELECT name FROM locations").scalar() == "Origen"
