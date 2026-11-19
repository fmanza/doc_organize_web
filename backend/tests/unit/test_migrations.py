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


# --- 0016: ai_settings de doc_organize 2.0 (W2) ------------------------------------------------------------------------

#: Filas sintéticas de 1.x: cuatro familias, con claves (cifradas, opacas para la migración) y modelos distintos, y una
#: URL distinta en la familia de un eje (que 2.0 no puede representar).
LEGACY_ROWS = [
    ("litellm_classification", "base_url", "https://proxy-uno.example", None),
    ("litellm_classification", "virtual_key", None, "gAAAA-clasificacion"),
    ("litellm_classification", "model", "modelo-un-eje", None),
    ("litellm_taxonomy_classification", "base_url", "https://proxy.example", None),
    ("litellm_taxonomy_classification", "virtual_key", None, "gAAAA-taxonomia"),
    ("litellm_taxonomy_classification", "model", "modelo-taxonomia", None),
    ("litellm_enrichment", "base_url", "https://proxy.example", None),
    ("litellm_enrichment", "virtual_key", None, "gAAAA-descripciones"),
    ("litellm_taxonomy_manifest_draft", "base_url", "https://proxy.example", None),
    ("litellm_taxonomy_manifest_draft", "virtual_key", None, "gAAAA-borrador"),
    ("litellm_taxonomy_manifest_draft", "model", "modelo-borrador", None),
    ("litellm_usage", "base_url", "https://proxy.example", None),
    ("litellm_usage", "virtual_key", None, "gAAAA-uso"),
    ("github_copilot_usage", "username", "octo-cat", None),
]


def _ai_rows(conn: object) -> set[tuple[str, str, str | None, str | None]]:
    rows = conn.exec_driver_sql("SELECT family, field, value, ciphertext FROM ai_settings")  # type: ignore[attr-defined]
    return {tuple(row) for row in rows}


def _insert_ai_rows(
    rows: list[tuple[str, str, str | None, str | None]], updated_at: str = "2026-01-01 00:00:00"
) -> None:
    with get_engine().begin() as conn:
        for family, field, value, ciphertext in rows:
            conn.exec_driver_sql(
                "INSERT INTO ai_settings (family, field, value, ciphertext, updated_at) VALUES (?, ?, ?, ?, ?)",
                (family, field, value, ciphertext, updated_at),
            )


def test_0016_moves_the_four_families_to_one_with_tasks_and_back(settings: Settings) -> None:
    """Ida y vuelta: cada tarea conserva su clave y su modelo; bajar sin cambios deja exactamente las filas de 1.x."""
    config = _config()
    command.upgrade(config, "0015")
    _insert_ai_rows(LEGACY_ROWS)

    command.upgrade(config, "0016")

    with get_engine().connect() as conn:
        migrated = _ai_rows(conn)
        assert conn.exec_driver_sql("SELECT count(*) FROM ai_settings_v1").scalar() == 11
    assert migrated == {
        ("litellm", "base_url", "https://proxy.example", None),  # la de taxonomía manda
        ("litellm", "virtual_key", None, "gAAAA-taxonomia"),
        ("litellm", "model_classify", "modelo-taxonomia", None),
        ("litellm", "virtual_key_enrich", None, "gAAAA-descripciones"),
        ("litellm", "virtual_key_taxonomy_design", None, "gAAAA-borrador"),
        ("litellm", "model_taxonomy_design", "modelo-borrador", None),
        ("litellm_usage", "base_url", "https://proxy.example", None),  # las de uso no cambian
        ("litellm_usage", "virtual_key", None, "gAAAA-uso"),
        ("github_copilot_usage", "username", "octo-cat", None),
    }

    command.downgrade(config, "0015")

    with get_engine().connect() as conn:
        assert _ai_rows(conn) == set(LEGACY_ROWS)
    assert "ai_settings_v1" not in inspect(get_engine()).get_table_names()


def test_0016_downgrade_rebuilds_from_what_changed_after_upgrading(settings: Settings) -> None:
    """Si se cambió la familia ``litellm`` tras subir, bajar rehace las cuatro familias desde ella (no restaura la copia)."""
    config = _config()
    command.upgrade(config, "0015")
    _insert_ai_rows([row for row in LEGACY_ROWS if row[0] == "litellm_enrichment"])
    command.upgrade(config, "0016")
    with get_engine().begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO ai_settings (family, field, value, updated_at) VALUES"
            " ('litellm', 'model_classify', 'modelo-nuevo', '2099-01-01 00:00:00')"
        )

    command.downgrade(config, "0015")

    with get_engine().connect() as conn:
        rows = _ai_rows(conn)
    for family in ("litellm_classification", "litellm_taxonomy_classification"):
        assert (family, "model", "modelo-nuevo", None) in rows
        assert (family, "virtual_key", None, "gAAAA-descripciones") in rows  # la general tras subir
    assert ("litellm_enrichment", "base_url", "https://proxy.example", None) in rows
    assert not any(family == "litellm" for family, *_ in rows)


def test_0016_without_ai_settings_is_a_no_op(settings: Settings) -> None:
    config = _config()
    command.upgrade(config, "0016")
    command.downgrade(config, "0015")
    with get_engine().connect() as conn:
        assert _ai_rows(conn) == set()
