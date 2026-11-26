"""La cadena de Alembic sube y baja entera (portabilidad, D8)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import CheckConstraint, Connection, inspect, text
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.db.base import Base
from app.db.session import get_engine
from tests import schema_snapshot

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _config() -> Config:
    return Config(str(BACKEND_DIR / "alembic.ini"))


def test_single_head() -> None:
    assert len(ScriptDirectory.from_config(_config()).get_heads()) == 1


def test_0033_matches_the_schema_snapshot(settings: Settings) -> None:
    """La BD en ``0033`` es exactamente ``tests/fixtures/schema_0033.sql``: la referencia del squash de la 3.0."""
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


# --- 0017: ejes del contexto, plantillas 2.0 y ajustes por proyecto (W2) ---------------------------------------------

TEMPLATE_V1 = """---
title: Sintética
domains:
  - slug: facturas
    name: Facturas
material_types:
  - slug: original
    name: Original
normative_frameworks:
  - slug: marco-a
    name: Marco A
---
# Notas
"""


def _seed_0016() -> None:
    """Un proyecto con un contexto de 1.x proyectado (plantilla, dos ejes) y una plantilla de 1.x: datos sintéticos."""
    with get_engine().begin() as conn:
        run = conn.exec_driver_sql
        run(
            "INSERT INTO users (id, tenant_id, username, display_name, password_hash, role_id, is_instance_admin,"
            " is_active, failed_attempts, password_changed_at, created_at, updated_at)"
            " SELECT 1, 1, 'ana', 'Ana', 'x', id, 0, 1, 0, '2026-01-01', '2026-01-01', '2026-01-01' FROM roles"
            " WHERE builtin = 'user' AND tenant_id = 1"
        )
        for id_, usage in ((1, "source"), (2, "destination")):
            run(
                "INSERT INTO locations (id, tenant_id, name, container_path, kind, usage, access, visibility, status,"
                " ignore_patterns, created_at, updated_at) VALUES (?, 1, ?, ?, 'local', ?, 'rw', 'global', 'ok', '[]',"
                " '2026-01-01', '2026-01-01')",
                (id_, f"L{id_}", f"/mnt/l{id_}", usage),
            )
        run(
            "INSERT INTO projects (id, tenant_id, name, source_location_id, source_subpaths, destination_location_id,"
            " destination_subpath, capture_owner, status, created_at, updated_at)"
            " VALUES (1, 1, 'P', 1, '[\"a\"]', 2, 'p', 0, 'active', '2026-01-01', '2026-01-01')"
        )
        run(
            "INSERT INTO project_contexts (project_id, output_folder_name, catalog_kind, documents_count,"
            " unclassified_count, failed_count, collisions_count, site_built, ai_classification, domains, built_at)"
            " VALUES (1, 'organizado', 'template', 1, 1, 0, 0, 0, 1,"
            ' \'[{"slug": "facturas", "name": "Facturas"}]\', \'2026-01-01\')'
        )
        run(
            "INSERT INTO context_documents (project_id, seq, domain_slug, title, material_type, material_type_name,"
            " folder, path, failed, collision, classified_by, keywords, ai_filled, rules_confidence, ai_confidence,"
            " material_type_confidence) VALUES"
            " (1, 0, 'facturas', 'Factura', 'original', 'Original', 'a', 'f.txt', 0, 0, 'ai', '[]', '[]', 0.2, 0.9, 0.7),"
            " (1, 1, NULL, 'Otro', NULL, NULL, 'a', 'o.txt', 0, 0, NULL, '[]', '[]', NULL, NULL, NULL)"
        )
        conn.execute(
            text(
                "INSERT INTO taxonomy_templates (tenant_id, name, markdown, created_at, updated_at)"
                " VALUES (1, 'sintetica', :m, '2026-01-01', '2026-01-01')"
            ),
            {"m": TEMPLATE_V1},
        )


def test_0017_backfills_axes_migrates_templates_and_goes_back(settings: Settings) -> None:
    config = _config()
    command.upgrade(config, "0016")
    _seed_0016()
    with get_engine().connect() as conn:
        before = {
            table: sorted(tuple(r) for r in conn.exec_driver_sql(f"SELECT * FROM {table}"))  # noqa: S608
            for table in ("projects", "project_contexts", "context_documents", "taxonomy_templates")
        }

    command.upgrade(config, "0017")

    with get_engine().connect() as conn:
        values = conn.exec_driver_sql(
            "SELECT seq, axis, slug, name, confidence, classified_by FROM context_document_axis_values ORDER BY axis"
        ).all()
        assert [tuple(v) for v in values] == [
            (0, "domains", "facturas", "Facturas", 0.9, "ai"),  # de la IA: su confianza
            (0, "material_types", "original", "Original", 0.7, "ai"),
        ]
        axes = json.loads(conn.exec_driver_sql("SELECT taxonomy_axes FROM project_contexts").scalar())
        assert [(a["key"], a["organizes"], [v["slug"] for v in a["values"]]) for a in axes] == [
            ("domains", "folder", ["facturas"]),
            ("material_types", "subfolder", ["original"]),
        ]
        markdown, original = conn.exec_driver_sql("SELECT markdown, markdown_v1 FROM taxonomy_templates").one()
        assert original == TEMPLATE_V1 and markdown.startswith("---\nschema: 2\n") and "marco-a" in markdown
        assert "# Notas" in markdown
        project = conn.exec_driver_sql(
            "SELECT ai_redact_credentials, context_versions, context_semantic FROM projects"
        ).one()
        assert tuple(project) == (1, "mark", 0)  # D7, D8 y D13
        conn.exec_driver_sql("DELETE FROM context_documents WHERE seq = 0")
        assert conn.exec_driver_sql("SELECT count(*) FROM context_document_axis_values").scalar() == 0  # CASCADE
        conn.rollback()

    command.downgrade(config, "0016")

    with get_engine().connect() as conn:
        after = {
            table: sorted(tuple(r) for r in conn.exec_driver_sql(f"SELECT * FROM {table}"))  # noqa: S608
            for table in before
        }
    assert after == before
    assert "context_document_axis_values" not in inspect(get_engine()).get_table_names()


# --- 0024: sin ai_settings_v1 (cierre de la 2.0.0) --------------------------------------------------------------------


def test_0024_drops_the_1x_copy_and_the_roundtrip_rebuilds_1x_from_2_0(settings: Settings) -> None:
    """0014 → head → 0014 con configuración: sin la copia, la 1.x se rehace desde la familia ``litellm``."""
    config = _config()
    command.upgrade(config, "0014")
    _insert_ai_rows(LEGACY_ROWS)

    command.upgrade(config, "head")
    assert "ai_settings_v1" not in inspect(get_engine()).get_table_names()

    command.downgrade(config, "0014")

    with get_engine().connect() as conn:
        rows = _ai_rows(conn)
    assert not any(family == "litellm" for family, *_ in rows)
    expected = {
        # Las dos de clasificación salen de la tarea `classify` (manda la de taxonomía al subir).
        ("litellm_taxonomy_classification", "base_url", "https://proxy.example", None),
        ("litellm_taxonomy_classification", "virtual_key", None, "gAAAA-taxonomia"),
        ("litellm_taxonomy_classification", "model", "modelo-taxonomia", None),
        ("litellm_classification", "base_url", "https://proxy.example", None),
        ("litellm_classification", "model", "modelo-taxonomia", None),
        ("litellm_enrichment", "virtual_key", None, "gAAAA-descripciones"),
        ("litellm_taxonomy_manifest_draft", "virtual_key", None, "gAAAA-borrador"),
        ("litellm_taxonomy_manifest_draft", "model", "modelo-borrador", None),
        ("litellm_usage", "base_url", "https://proxy.example", None),  # las de uso no cambian
        ("litellm_usage", "virtual_key", None, "gAAAA-uso"),
    }
    assert expected <= rows
    # La 0025 (web 2.1) borró GitHub Copilot y bajar no lo recupera.
    assert not any(family == "github_copilot_usage" for family, *_ in rows)
    assert ("litellm_classification", "model", "modelo-un-eje", None) not in rows  # lo que 2.0 no guardaba


def test_0024_roundtrip_without_ai_settings(settings: Settings) -> None:
    config = _config()
    command.upgrade(config, "0014")
    command.upgrade(config, "head")
    command.downgrade(config, "0014")
    with get_engine().connect() as conn:
        assert _ai_rows(conn) == set()
    assert "ai_settings_v1" not in inspect(get_engine()).get_table_names()


# --- 0025: sin GitHub Copilot (web 2.1) --------------------------------------------------------------------------------


def test_0025_drops_only_the_copilot_settings(settings: Settings) -> None:
    config = _config()
    command.upgrade(config, "0024")
    _insert_ai_rows(
        [
            ("github_copilot_usage", "username", "octo-cat", None),
            ("github_copilot_usage", "pat", None, "gAAAA-pat"),
            ("litellm_usage", "base_url", "https://proxy.example", None),
        ]
    )

    command.upgrade(config, "0025")
    with get_engine().connect() as conn:
        assert _ai_rows(conn) == {("litellm_usage", "base_url", "https://proxy.example", None)}

    command.downgrade(config, "0024")  # no recupera el secreto borrado
    with get_engine().connect() as conn:
        assert _ai_rows(conn) == {("litellm_usage", "base_url", "https://proxy.example", None)}


def test_roundtrip_script_accepts_the_rebuilt_ai_settings(settings: Settings, tmp_path: Path) -> None:
    """``scripts/migration_roundtrip.py`` sobre una base de la 1.x con IA: la 1.x rehecha desde 2.0 no es un fallo."""
    import shutil
    import subprocess
    import sys

    config = _config()
    command.upgrade(config, "0015")
    _insert_ai_rows(LEGACY_ROWS)
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
    assert "ai_settings: reconstruida desde la configuración de 2.0 (0024)" in result.stdout
    assert "gAAAA" not in result.stdout  # sin valores


# --- 0029: los proyectos borrados sueltan sus ubicaciones (web 2.3.1) -------------------------------------------------


def _insert_projects() -> None:
    """Dos ubicaciones y dos proyectos sobre ellas: «vivo» (activo) y «muerto» (borrado)."""
    with get_engine().begin() as conn:
        conn.execute(
            text(
                "INSERT INTO locations (id, tenant_id, name, container_path, kind, usage, access, status, visibility,"
                " created_at, updated_at) VALUES (:id, 1, :name, :path, 'local', 'both', 'rw', 'ok', 'global',"
                " '2026-01-01', '2026-01-01')"
            ),
            [
                {"id": 1, "name": "origen", "path": "/data/origen"},
                {"id": 2, "name": "destino", "path": "/data/destino"},
            ],
        )
        conn.execute(
            text(
                "INSERT INTO projects (id, tenant_id, name, source_location_id, source_subpaths,"
                " destination_location_id, destination_subpath, status, created_at, updated_at) VALUES"
                " (:id, 1, :name, 1, '[]', 2, :name, :status, '2026-01-01', '2026-01-01')"
            ),
            [{"id": 1, "name": "vivo", "status": "active"}, {"id": 2, "name": "muerto", "status": "deleted"}],
        )


def _project_locations(conn: Connection) -> dict[str, tuple[int | None, int | None]]:
    rows = conn.exec_driver_sql("SELECT name, source_location_id, destination_location_id FROM projects").all()
    return {name: (source, destination) for name, source, destination in rows}


def test_0029_releases_the_locations_of_deleted_projects(settings: Settings) -> None:
    config = _config()
    command.upgrade(config, "0028")
    _insert_projects()

    command.upgrade(config, "0029")
    with get_engine().connect() as conn:
        assert _project_locations(conn) == {"vivo": (1, 2), "muerto": (None, None)}
        with pytest.raises(IntegrityError):  # CHECK: un activo no puede quedarse sin ubicaciones
            conn.exec_driver_sql("UPDATE projects SET source_location_id = NULL WHERE name = 'vivo'")
        conn.rollback()
        with pytest.raises(IntegrityError):  # la FK sigue: RESTRICT mientras la use el activo
            conn.exec_driver_sql("DELETE FROM locations WHERE id = 1")
        conn.rollback()

    with pytest.raises(RuntimeError, match="Restaura la copia de seguridad"):
        command.downgrade(config, "0028")


def test_0029_downgrades_without_released_projects(settings: Settings) -> None:
    config = _config()
    command.upgrade(config, "0029")
    with get_engine().begin() as conn:
        conn.exec_driver_sql("DELETE FROM projects")

    command.downgrade(config, "0028")
    columns = {c["name"]: c["nullable"] for c in inspect(get_engine()).get_columns("projects")}
    assert columns["source_location_id"] is False
    assert columns["destination_location_id"] is False


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


def test_0031_adds_the_language_with_spanish_for_existing_users(settings: Settings) -> None:
    config = _config()
    command.upgrade(config, "0031")
    columns = {c["name"]: c for c in inspect(get_engine()).get_columns("users")}
    assert columns["language"]["nullable"] is False
    assert "es" in str(columns["language"]["default"])

    command.downgrade(config, "0030")
    assert "language" not in {c["name"] for c in inspect(get_engine()).get_columns("users")}


def test_0032_adds_the_actor_name_filled_with_each_username(settings: Settings) -> None:
    config = _config()
    command.upgrade(config, "0031")
    engine = get_engine()
    with engine.begin() as conn:
        role_id = conn.execute(text("SELECT id FROM roles LIMIT 1")).scalar_one()
        conn.execute(
            text(
                "INSERT INTO users (id, tenant_id, username, display_name, password_hash, role_id, is_instance_admin,"
                " is_active, failed_attempts, password_changed_at, created_at, updated_at)"
                " VALUES (90, 1, 'auditada', 'Auditada', 'x', :role, 0, 1, 0, '2026-11-25', '2026-11-25', '2026-11-25')"
            ),
            {"role": role_id},
        )
        conn.execute(
            text(
                "INSERT INTO audit_log (tenant_id, ts, actor_user_id, action, outcome)"
                " VALUES (1, '2026-11-25', 90, 'auth.login', 'success'), (1, '2026-11-25', NULL, 'system', 'success')"
            )
        )

    command.upgrade(config, "0032")
    with engine.begin() as conn:
        names = conn.execute(text("SELECT action, actor_name FROM audit_log ORDER BY id")).all()
    assert [tuple(row) for row in names][-2:] == [("auth.login", "auditada"), ("system", None)]

    command.downgrade(config, "0031")
    assert "actor_name" not in {c["name"] for c in inspect(get_engine()).get_columns("audit_log")}


def test_0033_adds_the_project_exclusions_empty_and_without_the_preset(settings: Settings) -> None:
    config = _config()
    command.upgrade(config, "0033")
    columns = {c["name"]: c for c in inspect(get_engine()).get_columns("projects")}
    for name in ("excluded_paths", "ignore_patterns", "exclude_system_folders"):
        assert columns[name]["nullable"] is False
    assert "[]" in str(columns["excluded_paths"]["default"])
    assert (
        "0" in str(columns["exclude_system_folders"]["default"])
        or "false" in str(columns["exclude_system_folders"]["default"]).lower()
    )

    command.downgrade(config, "0032")
    remaining = {c["name"] for c in inspect(get_engine()).get_columns("projects")}
    assert not remaining & {"excluded_paths", "ignore_patterns", "exclude_system_folders"}
