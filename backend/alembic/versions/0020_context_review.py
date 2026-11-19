"""Revisión de la clasificación (W5, doc_organize 2.0 F6): lo que hace falta para decidir sobre cada documento.

- ``context_documents``: ``document_key`` (clave de las decisiones: ruta del original relativa a la raíz de la
  ubicación de origen, ``<carpeta>/<ruta>``), ``source_sha256`` (huella del original, para que una decisión deje de
  aplicarse si cambia) y la versión del documento (``version``, ``version_group``, ``is_current``, con
  ``versions="mark"``). Índice ``(project_id, document_key)``.
- ``context_review_items``: la cola de ``review_queue`` de la última construcción (motivo, prioridad, eje, valor,
  confianza y detalle), con el documento si está en el contexto.
- ``project_contexts``: ``decisions_applied``, ``stale_decisions`` y ``orphan_decisions`` de la construcción.

Aditiva; los contextos ya proyectados los rellenan al reconstruir.

Revision ID: 0020
Revises: 0019
Create Date: 2026-11-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("context_documents") as batch:
        batch.add_column(sa.Column("document_key", sa.String(length=4096), nullable=True))
        batch.add_column(sa.Column("source_sha256", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("version", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("version_group", sa.String(length=4096), nullable=True))
        batch.add_column(sa.Column("is_current", sa.Boolean(), nullable=True))
    op.create_index("ix_context_documents_project_key", "context_documents", ["project_id", "document_key"])
    with op.batch_alter_table("project_contexts") as batch:
        batch.add_column(sa.Column("decisions_applied", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("stale_decisions", sa.JSON(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("orphan_decisions", sa.JSON(), nullable=False, server_default="[]"))
    op.create_table(
        "context_review_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=True),
        sa.Column("document_key", sa.String(length=4096), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("axis", sa.String(length=41), nullable=True),
        sa.Column("value", sa.String(length=128), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("detail", sa.String(length=1000), nullable=True),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["project_contexts.project_id"],
            name=op.f("fk_context_review_items_project_id_project_contexts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_context_review_items")),
    )
    op.create_index(
        "ix_context_review_items_project_priority", "context_review_items", ["project_id", "priority", "id"]
    )


def downgrade() -> None:
    op.drop_index("ix_context_review_items_project_priority", table_name="context_review_items")
    op.drop_table("context_review_items")
    with op.batch_alter_table("project_contexts") as batch:
        batch.drop_column("orphan_decisions")
        batch.drop_column("stale_decisions")
        batch.drop_column("decisions_applied")
    op.drop_index("ix_context_documents_project_key", table_name="context_documents")
    with op.batch_alter_table("context_documents") as batch:
        batch.drop_column("is_current")
        batch.drop_column("version_group")
        batch.drop_column("version")
        batch.drop_column("source_sha256")
        batch.drop_column("document_key")
