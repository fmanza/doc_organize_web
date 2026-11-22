"""Consumo de IA por ejecución (web 2.1, IA › Uso): tabla ``ai_usage`` y relleno desde las ejecuciones anteriores.

Una fila por ejecución y tarea con los recuentos (documentos enviados, caché, fallidos, tokens) y el modelo. Aditiva.

El relleno (D3) lee ``runs.result`` de las ejecuciones ya cerradas con IA. Usa su propia copia, **congelada**, de las
formas de resultado de la 2.0 (no importa ``app``: la migración no debe cambiar si el código cambia después). Lo que no
encaja se salta sin fallar. Las ejecuciones de la 2.0 no guardaban el modelo salvo la prueba de clasificación, así que
casi todo queda sin modelo.

Revision ID: 0026
Revises: 0025
Create Date: 2026-11-22
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CLOSED = ("succeeded", "cancelled", "failed")
_AI_OPERATIONS = ("context_build", "taxonomy_draft", "taxonomy_agent", "context_review_agent", "context_dry_run")


def upgrade() -> None:
    op.create_table(
        "ai_usage",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("project_name", sa.String(length=128), nullable=True),
        sa.Column("run_id", sa.String(length=36), nullable=True),
        sa.Column("operation", sa.String(length=32), nullable=False),
        sa.Column("task", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cached", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_estimated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_ai_usage_tenant_id_tenants"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_ai_usage_project_id_projects"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], name=op.f("fk_ai_usage_run_id_runs"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_usage")),
        sa.UniqueConstraint("run_id", "task", name="uq_ai_usage_run_task"),
    )
    op.create_index("ix_ai_usage_created_at", "ai_usage", ["created_at"])
    op.create_index("ix_ai_usage_project_created", "ai_usage", ["project_id", "created_at"])
    _backfill()


def downgrade() -> None:
    op.drop_index("ix_ai_usage_project_created", table_name="ai_usage")
    op.drop_index("ix_ai_usage_created_at", table_name="ai_usage")
    op.drop_table("ai_usage")


# --- relleno desde ``runs.result`` (formas de la 2.0, congeladas) ------------------------------------------------------

_runs = sa.table(
    "runs",
    sa.column("id", sa.String),
    sa.column("project_id", sa.Integer),
    sa.column("operation", sa.String),
    sa.column("status", sa.String),
    sa.column("result", sa.JSON),
    sa.column("created_at", sa.DateTime),
    sa.column("finished_at", sa.DateTime),
)
_projects = sa.table("projects", sa.column("id", sa.Integer), sa.column("tenant_id", sa.Integer), sa.column("name"))
_usage = sa.table(
    "ai_usage",
    sa.column("created_at", sa.DateTime),
    sa.column("tenant_id", sa.Integer),
    sa.column("project_id", sa.Integer),
    sa.column("project_name", sa.String),
    sa.column("run_id", sa.String),
    sa.column("operation", sa.String),
    sa.column("task", sa.String),
    sa.column("model", sa.String),
    sa.column("calls", sa.Integer),
    sa.column("cached", sa.Integer),
    sa.column("failed", sa.Integer),
    sa.column("prompt_tokens", sa.Integer),
    sa.column("completion_tokens", sa.Integer),
    sa.column("tokens_estimated", sa.Boolean),
)


def _int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 0


def _row(task: str, data: dict[str, Any], *, calls_key: str = "calls", **extra: Any) -> dict[str, Any] | None:
    row = {
        "task": task,
        "model": data.get("model") if isinstance(data.get("model"), str) else None,
        "calls": _int(data.get(calls_key)),
        "cached": _int(data.get("cached")),
        "failed": _int(data.get("failed")),
        "prompt_tokens": _int(data.get("prompt_tokens")),
        "completion_tokens": _int(data.get("completion_tokens")),
        "tokens_estimated": False,
        **extra,
    }
    used = row["calls"] or row["cached"] or row["prompt_tokens"] or row["completion_tokens"]
    return row if used else None


def _enabled(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) and value.get("enabled") else None


def _legacy_rows(operation: str, result: Any) -> list[dict[str, Any]]:
    if not isinstance(result, dict):
        return []
    found: list[dict[str, Any] | None] = []
    if operation == "context_build":
        if (ai := _enabled(result.get("ai"))) is not None:
            found.append(_row("classify", ai))
        if (enrich := _enabled(result.get("ai_enrichment"))) is not None:
            found.append(_row("enrich", enrich))
        if (semantic := _enabled(result.get("semantic"))) is not None:
            found.append(_row("embed", semantic, calls_key="embedded"))
    elif operation == "taxonomy_draft" and isinstance(result.get("manifest_markdown"), str):
        found.append(_row("taxonomy_design", {**result, "calls": 1}))
    elif operation in ("taxonomy_agent", "context_review_agent"):
        found.append(_row("agent", result, calls_key="steps"))
    elif operation == "context_dry_run" and isinstance(result.get("ai"), dict):
        ai = result["ai"]
        if ai.get("scope") not in (None, "off"):
            found.append(_row("classify", ai))
    return [row for row in found if row is not None]


def _backfill() -> None:
    conn = op.get_bind()
    projects = {row.id: row for row in conn.execute(sa.select(_projects.c.id, _projects.c.tenant_id, _projects.c.name))}
    query = sa.select(_runs).where(_runs.c.status.in_(_CLOSED), _runs.c.operation.in_(_AI_OPERATIONS))
    rows: list[dict[str, Any]] = []
    for run in conn.execute(query):
        found = _legacy_rows(run.operation, run.result)  # solo lee lo que reconoce: lo demás se salta
        project = projects.get(run.project_id)
        for row in found:
            rows.append(
                {
                    **row,
                    "created_at": run.finished_at or run.created_at,
                    "tenant_id": project.tenant_id if project is not None else None,
                    "project_id": run.project_id if project is not None else None,
                    "project_name": project.name if project is not None else None,
                    "run_id": run.id,
                    "operation": run.operation,
                }
            )
    if rows:
        op.bulk_insert(_usage, rows)
