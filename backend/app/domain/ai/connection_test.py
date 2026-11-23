"""«Probar conexión» de Configuración IA: prueba una familia con los valores del formulario, sin guardar nada.

Los campos que manda el formulario sustituyen a los efectivos (``ai_settings`` > ``DOC_ORGANIZE_*``); los demás se
toman de ahí, igual que al usar la familia. Dos reglas de seguridad:

- La clave guardada nunca se manda a una ``base_url`` distinta de la efectiva: con otra URL, hay que escribirla
  (``SecretRequiredError``). Si no, una sesión de admin robada bastaría para llevarse la clave a un servidor propio.
  En la familia ``litellm`` basta la clave general: las claves por tarea guardadas que no se escriban no se envían
  (la prueba usa la general).
- La respuesta solo dice si fue bien y con qué código falló, nunca el cuerpo de lo que contestó el servidor: así la
  prueba no sirve para leer URLs de la red interna.

Como mucho una prueba por familia cada ``MIN_TEST_INTERVAL_SECONDS`` (en memoria, por proceso): evita gastar tokens en
bucle con «Probar el modelo». Cada prueba se audita sin valores.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import User
from app.domain.ai import settings as ai_settings
from app.domain.ai.errors import AiNotConfiguredError, AiTestTooSoonError, InvalidAiSettingError, SecretRequiredError
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction, RequestContext
from app.integrations.doc_organize.ai import MODEL_FAMILIES, AiConnection, ConnectionCheck, TaskKey, check_connection

MIN_TEST_INTERVAL_SECONDS: Final = 10.0
#: Segundos máximos de cada petición de la prueba de conexión (como el panel de uso), sin reintentos.
MAX_TIMEOUT_SECONDS: Final = 10.0
#: Los de «Probar el modelo»: un modelo local (Ollama) tarda más de 10 s en cargarse si estaba descargado de memoria.
MAX_MODEL_TIMEOUT_SECONDS: Final = 60.0

_last_test: dict[str, float] = {}
_lock = threading.Lock()


def clear_rate_limit() -> None:
    """Olvida las últimas pruebas (tests)."""
    with _lock:
        _last_test.clear()


@dataclass(frozen=True)
class ProbeOutcome:
    """Resultado de una prueba, con la hora en que se hizo."""

    check: ConnectionCheck
    tested_at: datetime

    @property
    def ok(self) -> bool:
        return self.check.error is None


def _values(db: Session, settings: Settings, key: str, changes: dict[str, str | None]) -> dict[str, str]:
    """Valores con los que se prueba: los efectivos con los del formulario encima.

    Raises:
        InvalidAiSettingError: Campo ajeno o valor no válido.
        SecretRequiredError: Otra ``base_url`` sin escribir la clave.
        AiNotConfiguredError: Falta algún campo obligatorio.
    """
    spec = ai_settings.family_spec(key)
    validated = ai_settings.validate_changes(spec, changes)
    effective = ai_settings.resolve(db, settings, spec.key)
    values = dict(effective)
    for name, value in validated.items():
        if value is None:
            values.pop(name, None)
        else:
            values[name] = value
    url = validated.get("base_url")
    if url is not None and url != effective.get("base_url"):
        secrets = [field.name for field in spec.fields if field.secret]
        required = [field.name for field in spec.fields if field.secret and field.required]
        if any(not validated.get(name) for name in required):
            raise SecretRequiredError(
                "Con otra URL, escribe también la clave: la guardada no se envía a otro servidor."
            )
        for name in secrets:  # opcionales (claves por tarea) guardadas y no escritas: nunca a otro servidor
            if not validated.get(name):
                values.pop(name, None)
    missing = [field.name for field in spec.fields if field.required and field.name not in values]
    if missing:
        raise AiNotConfiguredError(f"Falta configurar {key}: {', '.join(missing)}")
    return values


def _claim(key: str, now: float) -> None:
    with _lock:
        last = _last_test.get(key)
        if last is not None and now - last < MIN_TEST_INTERVAL_SECONDS:
            raise AiTestTooSoonError(
                f"Vuelve a probar dentro de {int(MIN_TEST_INTERVAL_SECONDS - (now - last)) + 1} s."
            )
        _last_test[key] = now


def probe_family(
    db: Session,
    key: str,
    changes: dict[str, str | None],
    *,
    model_check: bool,
    settings: Settings,
    actor: User,
    ctx: RequestContext,
    task: TaskKey = "classify",
    clock: Callable[[], float] = time.monotonic,
) -> ProbeOutcome:
    """Prueba la familia ``key`` con ``changes`` encima de sus valores efectivos, sin guardar nada, y lo audita.

    En la familia ``litellm``, ``task`` elige qué modelo (y qué clave) se prueba con ``model_check``.

    Raises:
        AiFamilyNotFoundError: Familia desconocida.
        InvalidAiSettingError: Campo ajeno, valor no válido o ``model_check`` en una familia sin modelo.
        SecretRequiredError: Otra ``base_url`` sin escribir la clave.
        AiNotConfiguredError: Falta algún campo obligatorio.
        AiTestTooSoonError: Otra prueba de la familia hace menos de ``MIN_TEST_INTERVAL_SECONDS``.
    """
    spec = ai_settings.family_spec(key)
    if model_check and spec.key not in MODEL_FAMILIES:
        raise InvalidAiSettingError(f"{spec.key} no llama a un modelo: no hay modelo que probar")
    values = _values(db, settings, spec.key, changes)
    # 2.2: el límite es por modelo probado, para poder probar todas las tareas seguidas («Probar todo»).
    _claim(f"{spec.key}:{task}" if model_check else spec.key, clock())
    connection = AiConnection(
        family=spec.key,
        values=values,
        timeout_s=min(
            float(settings.ai_timeout_seconds), MAX_MODEL_TIMEOUT_SECONDS if model_check else MAX_TIMEOUT_SECONDS
        ),
        retries=0,
        budget=settings.ai_max_documents_per_run,
    )
    check = check_connection(connection, model_check=model_check, task=task)
    audit.record(
        db,
        action=AuditAction.AI_SETTINGS_TEST,
        ctx=ctx,
        actor_id=actor.id,
        target_type="ai_settings",
        target_id=spec.key,
        # Solo nombres de campo, nunca valores (ni los que no son secretos: pueden ser URLs internas).
        details={
            "model_check": model_check,
            "task": check.task,
            "error": check.error,
            "form_fields": sorted(changes),
        },
    )
    db.commit()
    return ProbeOutcome(check=check, tested_at=datetime.now(UTC))
