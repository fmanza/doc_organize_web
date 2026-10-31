from __future__ import annotations

import io

import pytest
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.cli import main
from app.core.config import Settings
from app.db.models import DEFAULT_TENANT_ID, Tenant, User
from app.db.session import get_engine
from tests.conftest import run_migrations


def test_create_admin_from_stdin(
    migrated: Settings, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("frase-de-paso-admin\n"))

    code = main(["create-admin", "--username", "Jefa", "--password-stdin"])

    assert code == 0
    out = capsys.readouterr()
    assert "jefa" in out.out
    assert "frase-de-paso-admin" not in out.out + out.err


def test_create_admin_rejects_duplicate_and_weak_password(
    migrated: Settings, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO("frase-de-paso-admin\n"))
    main(["create-admin", "--username", "jefa", "--password-stdin"])
    monkeypatch.setattr("sys.stdin", io.StringIO("frase-de-paso-admin\n"))
    assert main(["create-admin", "--username", "jefa", "--password-stdin"]) == 1

    monkeypatch.setattr("sys.stdin", io.StringIO("corta\n"))
    assert main(["create-admin", "--username", "otra", "--password-stdin"]) == 1
    assert "al menos" in capsys.readouterr().err


def test_migration_upgrade_downgrade_upgrade(settings: Settings) -> None:
    from alembic import command
    from alembic.config import Config

    from tests.conftest import BACKEND_DIR

    run_migrations()
    assert {"users", "sessions", "audit_log"} <= set(inspect(get_engine()).get_table_names())

    command.downgrade(Config(str(BACKEND_DIR / "alembic.ini")), "0001")
    assert "users" not in inspect(get_engine()).get_table_names()

    run_migrations()
    assert "users" in inspect(get_engine()).get_table_names()


def test_migration_creates_default_tenant_for_new_users(db: Session, admin: User) -> None:
    tenant = db.get(Tenant, DEFAULT_TENANT_ID)

    assert tenant is not None
    assert tenant.slug == "default"
    assert admin.tenant_id == DEFAULT_TENANT_ID
