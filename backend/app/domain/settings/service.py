"""Ajustes administrables (ADR-012): precedencia BD > variable ``DOW_*`` > valor por defecto, sin reiniciar.

Los ajustes **efectivos** son una copia de ``Settings`` con las filas de ``app_settings`` aplicadas: quien recibía
``Settings`` (identidad, ubicaciones) recibe los efectivos sin cambiar de firma. Se leen en cada petición. Solo se
admiten las claves de ``ADMIN_KEYS``, con los mismos rangos que ``Settings``; una fila fuera de rango se ignora y se
avisa en el log. Nunca se guardan secretos aquí.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import cache
from typing import Annotated, Any, Final, Literal, cast

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.db.models import AppSetting, User
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction, RequestContext

logger = logging.getLogger(__name__)

#: Claves administrables, en el orden en que se muestran.
ADMIN_KEYS: Final[tuple[str, ...]] = (
    "session_idle_minutes",
    "session_absolute_hours",
    "login_max_attempts",
    "login_lockout_minutes",
    "password_min_length",
    "location_probe_timeout_seconds",
    "location_latency_degraded_ms",
    "location_min_free_gb",
    "location_probe_interval_minutes",
    "run_retention_days",
    "user_quota_mb",
)

Source = Literal["db", "env", "default"]


class UnknownSettingError(AppError):
    """Clave no administrable."""

    title = "Ajuste desconocido"


class InvalidSettingError(AppError):
    """Valor fuera de rango o de otro tipo."""

    status = 422
    title = "Valor de ajuste no válido"


@dataclass(frozen=True)
class SettingView:
    """Un ajuste con su valor efectivo, el que tendría sin la fila de la BD y de dónde sale."""

    key: str
    value: Any
    default: Any
    source: Source


def _validate(key: str, value: Any) -> Any:
    """Valida ``value`` con el campo de ``Settings`` (tipo y rango).

    Raises:
        InvalidSettingError: Fuera de rango o de otro tipo.
    """
    try:
        return _adapter(key).validate_python(value, strict=True)
    except ValidationError as exc:
        first = exc.errors()[0]
        raise InvalidSettingError(f"{key}: {first['msg']}") from None


@cache
def _adapter(key: str) -> TypeAdapter[Any]:
    """Validador del campo ``key`` de ``Settings`` con su tipo y sus restricciones (``ge``/``le``)."""
    field = Settings.model_fields[key]
    # ``Annotated`` construido en tiempo de ejecución: mypy no puede tiparlo.
    return TypeAdapter(cast(Any, Annotated[field.annotation, *field.metadata]))


def overrides(db: Session) -> dict[str, Any]:
    """Valores guardados por un admin y válidos; uno fuera de rango se ignora (y se avisa)."""
    stored: dict[str, Any] = {}
    for row in db.scalars(select(AppSetting).where(AppSetting.key.in_(ADMIN_KEYS))):
        try:
            stored[row.key] = _validate(row.key, row.value)
        except InvalidSettingError:
            logger.warning("Ajuste administrable fuera de rango ignorado", extra={"key": row.key})
    return stored


def effective_settings(db: Session, settings: Settings) -> Settings:
    """``settings`` con los ajustes de los admins aplicados."""
    values = overrides(db)
    return settings.model_copy(update=values) if values else settings


def list_settings(db: Session, settings: Settings) -> list[SettingView]:
    """Ajustes administrables con su valor efectivo y su origen."""
    stored = overrides(db)
    return [
        SettingView(
            key=key,
            value=stored.get(key, getattr(settings, key)),
            default=getattr(settings, key),
            source="db" if key in stored else "env" if key in settings.model_fields_set else "default",
        )
        for key in ADMIN_KEYS
    ]


def update_settings(
    db: Session, changes: dict[str, Any], *, settings: Settings, actor: User, ctx: RequestContext
) -> list[SettingView]:
    """Guarda los cambios (``None`` = volver al valor de la variable o por defecto) y los audita.

    Se valida todo antes de escribir nada.

    Raises:
        UnknownSettingError: Alguna clave no es administrable.
        InvalidSettingError: Algún valor no es válido.
    """
    unknown = sorted(set(changes) - set(ADMIN_KEYS))
    if unknown:
        raise UnknownSettingError(f"No se pueden cambiar: {', '.join(unknown)}")
    validated = {key: None if value is None else _validate(key, value) for key, value in changes.items()}
    before = {view.key: view.value for view in list_settings(db, settings)}
    for key, value in validated.items():
        row = db.get(AppSetting, key)
        if value is None:
            if row is not None:
                db.delete(row)
        elif row is None:
            db.add(AppSetting(key=key, value=value, updated_by=actor.id))
        else:
            row.value = value
            row.updated_by = actor.id
    db.flush()
    after = list_settings(db, settings)
    changed = {view.key: [before[view.key], view.value] for view in after if before[view.key] != view.value}
    if changed:
        audit.record(
            db,
            action=AuditAction.SETTINGS_UPDATE,
            ctx=ctx,
            actor_id=actor.id,
            target_type="settings",
            details={"changes": changed},
        )
    db.commit()
    return after
