"""Metadatos y trazabilidad del contexto (1.5.0, doc_organize 1.5.0 ``DomainDocument`` y ``Context``).

Aditiva: las filas existentes quedan con nulos (y ``[]`` en las listas) hasta la siguiente construcción del contexto,
que sustituye la proyección entera.

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _document_columns() -> list[sa.Column[object]]:
    return [
        sa.Column("author", sa.String(500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("keywords", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("language", sa.String(8), nullable=True),
        sa.Column("ai_filled", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("rules_domain", sa.String(128), nullable=True),
        sa.Column("rules_confidence", sa.Float(), nullable=True),
        sa.Column("ai_domain", sa.String(128), nullable=True),
        sa.Column("ai_confidence", sa.Float(), nullable=True),
        sa.Column("ai_reasoning", sa.String(500), nullable=True),
        sa.Column("material_type_confidence", sa.Float(), nullable=True),
    ]


_CONTEXT_COLUMNS = ("built_with_version", "ai_classification_model", "ai_enrichment_model")


def upgrade() -> None:
    with op.batch_alter_table("context_documents") as batch:
        for column in _document_columns():
            batch.add_column(column)
        batch.create_index("ix_context_documents_project_language", ["project_id", "language"])
    with op.batch_alter_table("project_contexts") as batch:
        for name in _CONTEXT_COLUMNS:
            batch.add_column(sa.Column(name, sa.String(128), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("project_contexts") as batch:
        for name in reversed(_CONTEXT_COLUMNS):
            batch.drop_column(name)
    with op.batch_alter_table("context_documents") as batch:
        batch.drop_index("ix_context_documents_project_language")
        for column in reversed(_document_columns()):
            batch.drop_column(column.name)
