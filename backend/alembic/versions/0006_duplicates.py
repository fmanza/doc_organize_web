"""Duplicados (Fase 6): ``duplicate_groups`` con los grupos de cada vista previa.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "duplicate_groups",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("group_id", sa.String(length=36), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("member_count", sa.Integer(), nullable=False),
        sa.Column("members", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"], name=op.f("fk_duplicate_groups_run_id_runs"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("run_id", "group_id", name=op.f("pk_duplicate_groups")),
    )
    op.create_index(
        "ix_duplicate_groups_run_reason_position", "duplicate_groups", ["run_id", "reason", "position"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_duplicate_groups_run_reason_position", table_name="duplicate_groups")
    op.drop_table("duplicate_groups")
