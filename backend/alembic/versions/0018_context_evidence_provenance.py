"""Evidencia y procedencia del contexto (W3, doc_organize 2.0): ``context_document_axis_values.evidence`` (la cita
literal que dio la IA para un valor, D10) y ``project_contexts.ai_provenance`` (prompt y modelo de cada tarea de IA,
``Context.ai_provenance``). Aditiva: columnas nuevas, vacías en los contextos ya proyectados hasta reconstruir.

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("context_document_axis_values") as batch:
        batch.add_column(sa.Column("evidence", sa.String(length=500), nullable=True))
    with op.batch_alter_table("project_contexts") as batch:
        batch.add_column(sa.Column("ai_provenance", sa.JSON(), nullable=False, server_default="[]"))


def downgrade() -> None:
    with op.batch_alter_table("project_contexts") as batch:
        batch.drop_column("ai_provenance")
    with op.batch_alter_table("context_document_axis_values") as batch:
        batch.drop_column("evidence")
