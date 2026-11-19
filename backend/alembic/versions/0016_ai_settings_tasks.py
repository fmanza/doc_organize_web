"""IA de doc_organize 2.0 (W2): las cuatro familias ``litellm_*`` que llaman a un modelo pasan a una sola, ``litellm``,
con modelo, clave y presupuesto **por tarea** (cliente único ``LlmClient``, plan único §I).

Correspondencia (la de ``legacy_variables`` de la librería):

| 1.x | 2.0 (familia ``litellm``) |
|---|---|
| ``litellm_taxonomy_classification`` y ``litellm_classification`` | tarea ``classify`` |
| ``litellm_enrichment`` | tarea ``enrich`` |
| ``litellm_taxonomy_manifest_draft`` | tarea ``taxonomy_design`` |

- ``base_url`` y ``virtual_key`` generales salen de la primera familia configurada en el orden de la tabla (con las dos
  de clasificación, manda la de taxonomía: en 2.0 toda clasificación es por ejes).
- Cada tarea conserva **su** clave (``virtual_key_<tarea>``) y su modelo (``model_<tarea>``). Los secretos se copian
  cifrados tal cual: la migración no los descifra (no sabe si dos claves son la misma, así que cada tarea guarda la
  suya aunque coincida con la general; el resultado es el mismo).
- ``litellm_usage`` y ``github_copilot_usage`` no cambian. Los presupuestos por tarea (``budget_<tarea>``) son nuevos:
  sin fila, vale ``ai_max_documents_per_run``, como en 1.x.
- Lo que 2.0 no puede representar (dos URL distintas, o un modelo de ``litellm_classification`` distinto del de
  taxonomía) se avisa en el log de la migración y se conserva en ``ai_settings_v1``.

Las filas de 1.x se guardan en ``ai_settings_v1`` (con la hora de la migración) para que la bajada sea exacta: si nadie
cambió la familia ``litellm`` después, ``downgrade`` deja exactamente lo de antes; si se cambió, rehace las cuatro
familias desde ella (cada una con la URL, la clave de su tarea o la general, y su modelo).

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-19
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

logger = logging.getLogger("alembic.runtime.migration")

NEW_FAMILY = "litellm"
#: Familia de 1.x → tarea de 2.0, en orden de preferencia para la URL y la clave generales.
LEGACY: tuple[tuple[str, str], ...] = (
    ("litellm_taxonomy_classification", "classify"),
    ("litellm_classification", "classify"),
    ("litellm_enrichment", "enrich"),
    ("litellm_taxonomy_manifest_draft", "taxonomy_design"),
)
LEGACY_FAMILIES = tuple(family for family, _ in LEGACY)
COLUMNS = ("family", "field", "value", "ciphertext", "updated_by", "updated_at")

ai_settings = sa.table(
    "ai_settings",
    sa.column("family", sa.String),
    sa.column("field", sa.String),
    sa.column("value", sa.Text),
    sa.column("ciphertext", sa.Text),
    sa.column("updated_by", sa.Integer),
    sa.column("updated_at", sa.DateTime),
)
ai_settings_v1 = sa.table(
    "ai_settings_v1",
    sa.column("family", sa.String),
    sa.column("field", sa.String),
    sa.column("value", sa.Text),
    sa.column("ciphertext", sa.Text),
    sa.column("updated_by", sa.Integer),
    sa.column("updated_at", sa.DateTime),
    sa.column("migrated_at", sa.DateTime),
)

Row = dict[str, Any]


def _rows(conn: sa.Connection, table: Any, families: Sequence[str]) -> dict[str, dict[str, Row]]:
    """Familia → campo → fila (solo columnas de ``ai_settings``)."""
    found: dict[str, dict[str, Row]] = {}
    query = sa.select(*(table.c[name] for name in COLUMNS)).where(table.c.family.in_(families))
    for row in conn.execute(query).mappings():
        found.setdefault(row["family"], {})[row["field"]] = dict(row)
    return found


def _has_value(row: Row | None) -> bool:
    return row is not None and (row["value"] is not None or row["ciphertext"] is not None)


def _same(a: Row | None, b: Row | None) -> bool:
    """Mismo valor guardado (los secretos se comparan cifrados: dos copias de la misma clave cuentan como distintas)."""
    if a is None or b is None:
        return a is b
    return (a["value"], a["ciphertext"]) == (b["value"], b["ciphertext"])


def _copy(row: Row, field: str) -> Row:
    return {**row, "family": NEW_FAMILY, "field": field}


def tasks_from_legacy(legacy: dict[str, dict[str, Row]]) -> list[Row]:
    """Filas de la familia ``litellm`` a partir de las de 1.x (función pura: la prueban los tests de la migración)."""
    configured = [family for family in LEGACY_FAMILIES if family in legacy]
    if not configured:
        return []
    general_family = next(
        (f for f in configured if _has_value(legacy[f].get("base_url")) and _has_value(legacy[f].get("virtual_key"))),
        configured[0],
    )
    general = legacy[general_family]
    rows: list[Row] = []
    for field in ("base_url", "virtual_key"):
        row = general.get(field)
        if row is not None and _has_value(row):
            rows.append(_copy(row, field))
    done: set[str] = set()
    for family, task in LEGACY:
        source = legacy.get(family)
        if source is None:
            continue
        if task in done:  # la segunda familia de clasificación: lo que no cabe se queda en ai_settings_v1
            if not _same(source.get("model"), legacy[_first_of(task, legacy)].get("model")):
                logger.warning("0016: %s tenía otro modelo; classify usa el de la otra familia", family)
            continue
        done.add(task)
        model = source.get("model")
        if model is not None and _has_value(model):
            rows.append(_copy(model, f"model_{task}"))
        key = source.get("virtual_key")
        if key is not None and _has_value(key) and family != general_family:
            rows.append(_copy(key, f"virtual_key_{task}"))
        url = source.get("base_url")
        if _has_value(url) and not _same(url, general.get("base_url")):
            logger.warning(
                "0016: %s usaba otra base_url; 2.0 usa una para todas (se conserva en ai_settings_v1)", family
            )
    return rows


def _first_of(task: str, legacy: dict[str, dict[str, Row]]) -> str:
    return next(family for family, t in LEGACY if t == task and family in legacy)


def legacy_from_tasks(rows: dict[str, Row]) -> list[Row]:
    """Las cuatro familias de 1.x desde los campos de ``litellm`` (para ``downgrade`` cuando se cambió después)."""
    if not (_has_value(rows.get("base_url")) or _has_value(rows.get("virtual_key"))):
        return []
    restored: list[Row] = []
    for family, task in LEGACY:
        sources = {
            "base_url": rows.get("base_url"),
            "virtual_key": rows.get(f"virtual_key_{task}") or rows.get("virtual_key"),
            "model": rows.get(f"model_{task}"),
        }
        for field, row in sources.items():
            if row is not None and _has_value(row):
                restored.append({**row, "family": family, "field": field})
    return restored


def upgrade() -> None:
    op.create_table(
        "ai_settings_v1",
        sa.Column("family", sa.String(length=64), nullable=False),
        sa.Column("field", sa.String(length=32), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("ciphertext", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("migrated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("family", "field", name=op.f("pk_ai_settings_v1")),
    )
    conn = op.get_bind()
    legacy = _rows(conn, ai_settings, LEGACY_FAMILIES)
    migrated_at = datetime.now(UTC).replace(tzinfo=None)
    backup = [{**row, "migrated_at": migrated_at} for fields in legacy.values() for row in fields.values()]
    if backup:
        conn.execute(sa.insert(ai_settings_v1), backup)
    new_rows = tasks_from_legacy(legacy)
    conn.execute(sa.delete(ai_settings).where(ai_settings.c.family.in_(LEGACY_FAMILIES)))
    conn.execute(sa.delete(ai_settings).where(ai_settings.c.family == NEW_FAMILY))
    if new_rows:
        conn.execute(sa.insert(ai_settings), new_rows)


def downgrade() -> None:
    conn = op.get_bind()
    current = _rows(conn, ai_settings, (NEW_FAMILY,)).get(NEW_FAMILY, {})
    backup_rows = [dict(row) for row in conn.execute(sa.select(ai_settings_v1)).mappings()]
    migrated_at = max((_naive(row["migrated_at"]) for row in backup_rows), default=None)
    unchanged = migrated_at is not None and all(_naive(row["updated_at"]) <= migrated_at for row in current.values())
    if backup_rows and unchanged:
        restored = [{name: row[name] for name in COLUMNS} for row in backup_rows]
    else:
        restored = legacy_from_tasks(current)
    conn.execute(sa.delete(ai_settings).where(ai_settings.c.family.in_((NEW_FAMILY, *LEGACY_FAMILIES))))
    if restored:
        conn.execute(sa.insert(ai_settings), restored)
    op.drop_table("ai_settings_v1")


def _naive(value: datetime | str) -> datetime:
    """``updated_at`` como lo devuelve SQLite (texto) o PostgreSQL (``datetime``), sin zona, para comparar."""
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return value.replace(tzinfo=None) if value.tzinfo else value
