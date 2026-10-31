"""Sondeo de ubicaciones y precedencia de los ajustes administrables (ADR-007, ADR-012)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import AppSetting, User
from app.domain.identity.audit import CLI_CONTEXT
from app.domain.locations import probe as probe_module
from app.domain.locations.probe import probe
from app.domain.settings.service import (
    InvalidSettingError,
    UnknownSettingError,
    effective_settings,
    list_settings,
    update_settings,
)


def _settings(**values: int) -> Settings:
    return Settings(**{"environment": "test", "location_min_free_gb": 0, **values})  # type: ignore[arg-type]


def test_probe_ok_and_write_only_checked_for_rw(tmp_path: Path) -> None:
    ro = probe(tmp_path, access="ro", settings=_settings())
    rw = probe(tmp_path, access="rw", settings=_settings())

    assert (ro.status, ro.writable, ro.reasons) == ("ok", None, [])
    assert (rw.status, rw.writable) == ("ok", True)
    assert rw.latency_ms is not None
    assert rw.free_bytes is not None
    assert list(tmp_path.iterdir()) == []  # el fichero temporal de la prueba de escritura se borra


def test_probe_missing_folder_is_unavailable(tmp_path: Path) -> None:
    result = probe(tmp_path / "no-esta", access="ro", settings=_settings())

    assert (result.status, result.reasons) == ("unavailable", ["missing"])


def test_probe_low_space_and_not_writable_are_degraded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _fail(*_: object, **__: object) -> None:
        raise PermissionError("solo lectura")

    monkeypatch.setattr(Path, "write_bytes", _fail)

    result = probe(tmp_path, access="rw", settings=_settings(location_min_free_gb=100_000))

    assert result.status == "degraded"
    assert result.reasons == ["low_space", "not_writable"]
    assert result.writable is False


def test_probe_hung_mount_is_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(probe_module, "_measure", lambda *_, **__: time.sleep(3))

    result = probe(tmp_path, access="ro", settings=_settings(location_probe_timeout_seconds=1))

    assert (result.status, result.reasons) == ("unavailable", ["timeout"])


def test_settings_precedence_db_over_env_over_default(
    db: Session, admin: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DOW_LOGIN_LOCKOUT_MINUTES", "30")
    base = Settings()  # type: ignore[call-arg]
    update_settings(db, {"login_max_attempts": 3}, settings=base, actor=admin, ctx=CLI_CONTEXT)

    views = {view.key: view for view in list_settings(db, base)}
    effective = effective_settings(db, base)

    assert (views["login_max_attempts"].value, views["login_max_attempts"].source) == (3, "db")
    assert (views["login_lockout_minutes"].value, views["login_lockout_minutes"].source) == (30, "env")
    assert views["password_min_length"].source == "default"
    assert (effective.login_max_attempts, effective.login_lockout_minutes) == (3, 30)


def test_settings_null_restores_default(db: Session, admin: User) -> None:
    base = Settings()  # type: ignore[call-arg]
    update_settings(db, {"password_min_length": 16}, settings=base, actor=admin, ctx=CLI_CONTEXT)
    update_settings(db, {"password_min_length": None}, settings=base, actor=admin, ctx=CLI_CONTEXT)

    assert effective_settings(db, base).password_min_length == 12
    assert db.get(AppSetting, "password_min_length") is None


@pytest.mark.parametrize(
    ("changes", "error"),
    [
        ({"password_min_length": 7}, InvalidSettingError),
        ({"login_max_attempts": True}, InvalidSettingError),
        ({"app_secret_key": "x"}, UnknownSettingError),
    ],
)
def test_settings_reject_out_of_range_wrong_type_and_unknown(
    db: Session, admin: User, changes: dict[str, object], error: type[Exception]
) -> None:
    with pytest.raises(error):
        update_settings(db, changes, settings=Settings(), actor=admin, ctx=CLI_CONTEXT)  # type: ignore[call-arg]


def test_out_of_range_row_in_db_is_ignored(db: Session, caplog: pytest.LogCaptureFixture) -> None:
    db.add(AppSetting(key="password_min_length", value=3))
    db.commit()

    assert effective_settings(db, Settings()).password_min_length == 12  # type: ignore[call-arg]
    assert "fuera de rango" in caplog.text
