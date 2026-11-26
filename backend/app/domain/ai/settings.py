"""Configuración de las 3 familias de IA (WB-8.1, ADR-004; doc_organize 2.0, W2).

Desde 2.0 una sola familia, ``litellm``, configura todas las tareas de IA (clasificar, describir, diseñar la taxonomía,
agentes y embeddings): URL y clave general obligatorias y, por tarea, modelo, clave propia y presupuesto opcionales. La
migración ``0016`` pasó a ella las cuatro familias de 1.x. ``litellm_usage`` no cambia; ``github_copilot_usage`` se
quitó en la 2.1 (migración ``0025``).

Precedencia: valor guardado por un admin en ``ai_settings`` > variable ``DOC_ORGANIZE_*`` del entorno (los mismos
nombres que la librería: ``DOC_ORGANIZE_LITELLM_BASE_URL``, ``_VIRTUAL_KEY``, ``_MODEL_<TAREA>``,
``_VIRTUAL_KEY_<TAREA>``). Las variables de 1.x (``DOC_ORGANIZE_LITELLM_<CLIENTE>_*``) y las de GitHub Copilot no se
leen ni se avisa de ellas (3.0). Los campos secretos se guardan cifrados con MultiFernet. Nunca se devuelven, ni se auditan, ni se escriben en un log: solo se muestra que están configurados y su ``hint``
(«…ab12» o, si miden 4 caracteres o menos, «***»). Un token que no se descifra (porque se retiró la clave con la que se
cifró) cuenta como «sin valor» y se marca ``undecryptable``.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Final, Literal
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import crypto
from app.core.config import Settings
from app.db.models import AiSetting, User
from app.domain.ai.errors import (
    AiFamilyNotFoundError,
    AiNotConfiguredError,
    EncryptionNotConfiguredError,
    InvalidAiSettingError,
)
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction, RequestContext
from app.integrations.doc_organize.ai import (
    FAMILIES,
    FAMILIES_BY_KEY,
    OWN_MODEL_TASKS,
    TASKS,
    AiConnection,
    FamilyKey,
    FamilySpec,
    FieldSpec,
    TaskKey,
)

logger = logging.getLogger(__name__)

Source = Literal["db", "env", "none"]

#: Caracteres finales de un secreto que se muestran (lo justo para reconocerlo, nunca para reconstruirlo).
HINT_SUFFIX: Final = 4
MAX_URL_LENGTH: Final = 2048
MAX_SECRET_LENGTH: Final = 4096
_MODEL_RE: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@-]{0,127}$")
_CONTROL_RE: Final = re.compile(r"[\x00-\x20\x7f]")
#: Presupuesto de documentos por tarea (mismos límites que ``ai_max_documents_per_run``).
MAX_BUDGET: Final = 100_000


@dataclass(frozen=True)
class FieldView:
    """Estado de un campo. ``value`` solo en los no secretos; ``hint`` solo en los secretos. ``task`` es la tarea del
    campo en la familia ``litellm`` (``None`` = de todas)."""

    name: str
    env_var: str | None
    secret: bool
    required: bool
    source: Source
    value: str | None
    hint: str | None
    undecryptable: bool = False
    task: str | None = None


@dataclass(frozen=True)
class FamilyView:
    key: FamilyKey
    configured: bool
    fields: list[FieldView]


def family_spec(key: str) -> FamilySpec:
    """La familia ``key``.

    Raises:
        AiFamilyNotFoundError: No es una de las 3.
    """
    spec = FAMILIES_BY_KEY.get(key)
    if spec is None:
        raise AiFamilyNotFoundError()
    return spec


def hint(value: str) -> str:
    """«…» y los 4 últimos caracteres; «***» si el valor es tan corto que el sufijo lo revelaría entero."""
    return f"…{value[-HINT_SUFFIX:]}" if len(value) > HINT_SUFFIX else "***"


def _rows(db: Session, family: str | None = None) -> dict[tuple[str, str], AiSetting]:
    query = select(AiSetting)
    if family is not None:
        query = query.where(AiSetting.family == family)
    return {(row.family, row.field): row for row in db.scalars(query)}


def _stored(settings: Settings, row: AiSetting | None) -> tuple[str | None, bool]:
    """Valor guardado de ``row`` (descifrado si es secreto) y si no se pudo descifrar."""
    if row is None:
        return None, False
    if row.ciphertext is None:
        return row.value or None, False
    try:
        return crypto.decrypt(settings, row.ciphertext) or None, False
    except (crypto.EncryptionNotConfiguredError, crypto.UndecryptableError):
        logger.warning("Credencial de IA guardada que no se puede descifrar", extra={"family": row.family})
        return None, True


def _field_view(settings: Settings, spec: FieldSpec, row: AiSetting | None) -> tuple[FieldView, str | None]:
    stored, undecryptable = _stored(settings, row)
    env = (os.environ.get(spec.env_var) or None) if spec.env_var else None
    value = stored or env
    source: Source = "db" if stored else "env" if env else "none"
    view = FieldView(
        name=spec.name,
        env_var=spec.env_var,
        secret=spec.secret,
        required=spec.required,
        source=source,
        value=None if spec.secret else value,
        hint=hint(value) if spec.secret and value else None,
        undecryptable=undecryptable,
        task=spec.task,
    )
    return view, value


def _family_view(settings: Settings, spec: FamilySpec, rows: dict[tuple[str, str], AiSetting]) -> FamilyView:
    views = [_field_view(settings, field, rows.get((spec.key, field.name))) for field in spec.fields]
    configured = all(value for (view, value) in views if view.required)
    return FamilyView(key=spec.key, configured=configured, fields=[view for view, _ in views])


def list_families(db: Session, settings: Settings) -> list[FamilyView]:
    """Las 3 familias con el estado de cada campo (sin ningún secreto)."""
    rows = _rows(db)
    return [_family_view(settings, spec, rows) for spec in FAMILIES]


def configured_families(db: Session, settings: Settings) -> dict[str, bool]:
    """Familia → si tiene todos sus campos obligatorios (para cualquier usuario: sin valores)."""
    return {view.key: view.configured for view in list_families(db, settings)}


def configured_tasks(db: Session, settings: Settings) -> dict[str, bool]:
    """Tarea de IA → si se puede usar: todas dependen de la familia ``litellm`` (sin modelo, el alias recomendado),
    salvo las de ``OWN_MODEL_TASKS`` (2.2: duplicados por contenido), que además necesitan su propio modelo."""
    configured = configured_families(db, settings).get("litellm", False)
    values = resolve(db, settings, "litellm") if configured else {}
    return {task: configured and (task not in OWN_MODEL_TASKS or bool(values.get(f"model_{task}"))) for task in TASKS}


def require_task(db: Session, settings: Settings, task: TaskKey) -> None:
    """Que la tarea ``task`` se pueda usar (``configured_tasks``).

    Raises:
        AiNotConfiguredError: Falta la familia ``litellm`` o, en las de ``OWN_MODEL_TASKS``, su modelo propio.
    """
    if not configured_tasks(db, settings).get(task, False):
        detail = (
            f"La tarea de IA «{task}» necesita su propio modelo: configúralo en IA › Modelos."
            if task in OWN_MODEL_TASKS
            else "Configura los modelos de IA en IA › Modelos."
        )
        raise AiNotConfiguredError(detail)


def resolve(db: Session, settings: Settings, key: FamilyKey) -> dict[str, str]:
    """Valores efectivos de la familia ``key`` (solo los que tienen valor). Uso interno: lleva los secretos."""
    spec = family_spec(key)
    rows = _rows(db, key)
    values: dict[str, str] = {}
    for field in spec.fields:
        _, value = _field_view(settings, field, rows.get((key, field.name)))
        if value:
            values[field.name] = value
    return values


def connection(db: Session, settings: Settings, key: FamilyKey) -> AiConnection:
    """Conexión de la familia ``key`` con los ajustes de timeout, reintentos y presupuesto vigentes.

    Las tareas largas (borrador de manifiesto y agentes) llevan su propio plazo y sus reintentos
    (``ai_draft_timeout_seconds``/``ai_draft_retries``), que doc_organize 2.0.0rc1 aplica por tarea.

    Raises:
        AiNotConfiguredError: Le falta algún campo obligatorio.
    """
    spec = family_spec(key)
    values = resolve(db, settings, key)
    missing = [field.name for field in spec.fields if field.required and field.name not in values]
    if missing:
        raise AiNotConfiguredError(f"Falta configurar {key}: {', '.join(missing)}")
    return AiConnection(
        family=key,
        values=values,
        timeout_s=float(settings.ai_timeout_seconds),
        retries=settings.ai_retries,
        long_timeout_s=float(settings.ai_draft_timeout_seconds),
        long_retries=settings.ai_draft_retries,
        budget=settings.ai_max_documents_per_run,
    )


def require_configured(db: Session, settings: Settings, key: FamilyKey) -> None:
    """Comprueba al encolar que ``key`` está configurada (el job vuelve a resolverla en el subproceso).

    Raises:
        AiNotConfiguredError: Le falta algún campo obligatorio.
    """
    connection(db, settings, key)


def validate_base_url(value: str) -> str:
    """``value`` si es una URL http/https con host, sin credenciales, *query* ni fragmento.

    Raises:
        InvalidAiSettingError: No lo es.
    """
    if len(value) > MAX_URL_LENGTH or _CONTROL_RE.search(value):
        raise InvalidAiSettingError("base_url: URL demasiado larga o con espacios")
    try:
        parts = urlsplit(value)
        port = parts.port  # valida el puerto
    except ValueError:
        raise InvalidAiSettingError("base_url: no es una URL válida") from None
    del port
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise InvalidAiSettingError("base_url: tiene que ser http:// o https:// con un servidor")
    if parts.username is not None or parts.password is not None:
        raise InvalidAiSettingError("base_url: sin usuario ni contraseña en la URL (la clave va aparte)")
    if parts.query or parts.fragment:
        raise InvalidAiSettingError("base_url: sin parámetros ni fragmento")
    return value.rstrip("/")


def validate_changes(spec: FamilySpec, changes: dict[str, str | None]) -> dict[str, str | None]:
    """``changes`` validados con las reglas de cada campo (``None`` o ``""`` = sin valor), sin escribir nada.

    Raises:
        InvalidAiSettingError: Campo ajeno o valor no válido.
    """
    validated: dict[str, str | None] = {}
    for name, raw in changes.items():
        field = spec.field(name)
        if field is None:
            raise InvalidAiSettingError(f"«{name}» no es un campo de {spec.key}")
        text = (raw or "").strip()
        validated[name] = _validate(field, text) if text else None
    return validated


def _validate(spec: FieldSpec, value: str) -> str:
    if spec.name == "base_url":
        return validate_base_url(value)
    if spec.secret:
        if len(value) > MAX_SECRET_LENGTH or _CONTROL_RE.search(value):
            raise InvalidAiSettingError(f"{spec.name}: demasiado largo o con espacios")
        return value
    if spec.name.startswith("model") and not _MODEL_RE.fullmatch(value):
        raise InvalidAiSettingError(f"{spec.name}: alias de modelo no válido")
    if spec.name.startswith("budget_"):
        if not value.isdigit() or not 1 <= int(value) <= MAX_BUDGET:
            raise InvalidAiSettingError(f"{spec.name}: número de documentos entre 1 y {MAX_BUDGET}")
        return str(int(value))
    return value


def update_family(
    db: Session,
    key: str,
    changes: dict[str, str | None],
    *,
    settings: Settings,
    actor: User,
    ctx: RequestContext,
) -> FamilyView:
    """Guarda o borra campos de la familia ``key`` (ausente = no se toca; ``None`` o ``""`` = borrar) y lo audita.

    Se valida todo antes de escribir nada. En la auditoría van los nombres de los campos y, solo para los no secretos,
    el valor anterior y el nuevo.

    Raises:
        AiFamilyNotFoundError: Familia desconocida.
        InvalidAiSettingError: Campo ajeno o valor no válido.
        EncryptionNotConfiguredError: Hay que cifrar un secreto y no hay ``DOW_FERNET_KEYS``.
    """
    spec = family_spec(key)
    validated = validate_changes(spec, changes)
    specs = {field.name: field for field in spec.fields}
    if any(value and specs[name].secret for name, value in validated.items()) and not crypto.is_configured(settings):
        raise EncryptionNotConfiguredError("Define DOW_FERNET_KEYS para guardar credenciales")

    rows = _rows(db, key)
    changed: list[str] = []
    cleared: list[str] = []
    values: dict[str, list[str | None]] = {}
    for name, value in validated.items():
        field = specs[name]
        row = rows.get((key, name))
        old, _ = _stored(settings, row)
        if value is None:
            if row is not None:
                db.delete(row)
                cleared.append(name)
            continue
        if old == value:
            continue
        if row is None:
            row = AiSetting(family=key, field=name)
            db.add(row)
        row.value = None if field.secret else value
        row.ciphertext = crypto.encrypt(settings, value) if field.secret else None
        row.updated_by = actor.id
        changed.append(name)
        if not field.secret:
            values[name] = [old, value]
    db.flush()
    if changed or cleared:
        audit.record(
            db,
            action=AuditAction.AI_SETTINGS_UPDATE,
            ctx=ctx,
            actor_id=actor.id,
            target_type="ai_settings",
            target_id=key,
            details={"changed": changed, "cleared": cleared, "values": values},
        )
    db.commit()
    return _family_view(settings, spec, _rows(db, key))


@dataclass(frozen=True)
class RotateResult:
    rotated: int
    failed: int


def rotate_all(db: Session, settings: Settings) -> RotateResult:
    """Vuelve a cifrar con la primera clave todos los secretos guardados (``python -m app.cli rotate-secrets``).

    Un token que no descifra ninguna clave se deja como está y se cuenta en ``failed``.

    Raises:
        crypto.EncryptionNotConfiguredError: No hay claves.
    """
    crypto.cipher(settings)
    rotated = failed = 0
    for row in db.scalars(select(AiSetting).where(AiSetting.ciphertext.is_not(None))):
        try:
            row.ciphertext = crypto.rotate(settings, row.ciphertext or "")
        except crypto.UndecryptableError:
            failed += 1
            continue
        rotated += 1
    db.commit()
    return RotateResult(rotated=rotated, failed=failed)
