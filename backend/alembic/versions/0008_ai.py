"""IA (Fase 8): ``ai_settings`` cifrado, ``project_contexts.ai_classification`` y ``context_documents.classified_by``.

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_settings",
        sa.Column("family", sa.String(length=64), nullable=False),
        sa.Column("field", sa.String(length=32), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("ciphertext", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("(value IS NULL) <> (ciphertext IS NULL)", name=op.f("ck_ai_settings_one_value")),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["users.id"], name=op.f("fk_ai_settings_updated_by_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("family", "field", name=op.f("pk_ai_settings")),
    )
    with op.batch_alter_table("project_contexts") as batch:
        batch.add_column(sa.Column("ai_classification", sa.Boolean(), nullable=False, server_default=sa.false()))
    with op.batch_alter_table("context_documents") as batch:
        batch.add_column(sa.Column("classified_by", sa.String(length=8), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("context_documents") as batch:
        batch.drop_column("classified_by")
    with op.batch_alter_table("project_contexts") as batch:
        batch.drop_column("ai_classification")
    op.drop_table("ai_settings")
