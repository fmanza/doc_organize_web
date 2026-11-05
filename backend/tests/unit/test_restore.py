"""Fase 10 (WB-10.4): simulacro de restauración de ``config.db`` y las cachés, con vista previa y sus negativas."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app import cli
from app.core.config import Settings
from app.db import backup
from app.db.models import User, Worker, utcnow


def _cache(settings: Settings, value: str) -> Path:
    path = settings.data_dir / "projects" / "1" / "folders" / "raiz" / "cache.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS t (v TEXT)")
        conn.execute("DELETE FROM t")
        conn.execute("INSERT INTO t VALUES (?)", (value,))
        conn.commit()
    return path


def _value(path: Path) -> str:
    with closing(sqlite3.connect(path)) as conn:
        return str(conn.execute("SELECT v FROM t").fetchone()[0])


def test_restore_brings_back_config_and_caches(migrated: Settings, db: Session, admin: User, tmp_path: Path) -> None:
    cache = _cache(migrated, "antes")
    copy = backup.create_backup(migrated, destination=tmp_path / "copias")
    # Después de la copia: otro usuario y la caché cambia.
    admin.display_name = "Cambiado"
    db.commit()
    _cache(migrated, "después")

    plan = backup.restore_plan(migrated, copy)
    assert {(item.path, item.replaces) for item in plan} == {
        ("config.db", True),
        ("projects/1/folders/raiz/cache.db", True),
    }
    backup.restore_backup(migrated, copy)

    db.expire_all()
    assert db.get(User, admin.id).display_name == "Admin"  # type: ignore[union-attr]
    assert _value(cache) == "antes"
    saved = [p.name for p in cache.parent.iterdir() if ".pre-restore-" in p.name]
    assert len(saved) == 1 and _value(cache.parent / saved[0]) == "después"
    assert any(".pre-restore-" in p.name for p in migrated.data_dir.iterdir())


def test_restore_refuses_while_a_worker_is_alive(migrated: Settings, db: Session, tmp_path: Path) -> None:
    copy = backup.create_backup(migrated, destination=tmp_path / "copias")
    db.add(Worker(id="w1", queues=["cpu"], version="x", started_at=utcnow(), heartbeat_at=utcnow()))
    db.commit()

    with pytest.raises(backup.RestoreError, match="worker"):
        backup.restore_backup(migrated, copy)

    db.query(Worker).update({Worker.heartbeat_at: utcnow() - timedelta(hours=1)})  # caído hace tiempo: no cuenta
    db.commit()
    backup.restore_backup(migrated, copy)


def test_restore_refuses_a_tampered_or_foreign_copy(migrated: Settings, tmp_path: Path) -> None:
    copy = backup.create_backup(migrated, destination=tmp_path / "copias")
    manifest = json.loads((copy / backup.MANIFEST).read_text(encoding="utf-8"))
    manifest["files"][0]["sha256"] = "0" * 64
    (copy / backup.MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(backup.RestoreError, match="no es válida"):
        backup.restore_plan(migrated, copy)

    other = tmp_path / "otra"
    (other / "secrets").mkdir(parents=True)
    with closing(sqlite3.connect(other / "secrets" / "x.db")) as conn:
        conn.execute("CREATE TABLE t (v)")
    entry = {"path": "secrets/x.db", "size": 0, "sha256": backup._sha256(other / "secrets" / "x.db")}
    (other / backup.MANIFEST).write_text(json.dumps({"files": [entry]}), encoding="utf-8")

    with pytest.raises(backup.RestoreError, match="no es una base de datos de la aplicación"):
        backup.restore_plan(migrated, other)


def test_cli_restore_previews_without_yes(
    migrated: Settings, admin: User, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    copy = backup.create_backup(migrated, destination=tmp_path / "copias")
    before = (migrated.data_dir / "config.db").stat().st_mtime_ns

    assert cli.main(["restore", str(copy)]) == 0

    assert "Vista previa" in capsys.readouterr().out
    assert (migrated.data_dir / "config.db").stat().st_mtime_ns == before
    assert not any(".pre-restore-" in p.name for p in migrated.data_dir.iterdir())
    assert cli.main(["restore", str(copy), "--yes"]) == 0
    assert "Copia restaurada" in capsys.readouterr().out
