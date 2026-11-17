"""Versiones del manifiesto de taxonomía (1.8.0): lo que había antes de guardar, borrar, restaurar o vaciar el
histórico, para poder deshacerlo. Aditiva: tabla nueva, sin tocar las existentes.

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_manifest_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("markdown", sa.Text(), nullable=True),
        sa.Column("domains", sa.Integer(), nullable=True),
        sa.Column("material_types", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "action IN ('save', 'delete', 'restore', 'history_clear')",
            name=op.f("ck_project_manifest_versions_action"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_project_manifest_versions_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_project_manifest_versions_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project_manifest_versions")),
    )
    op.create_index(
        "ix_project_manifest_versions_project_created",
        "project_manifest_versions",
        ["project_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_project_manifest_versions_project_created", table_name="project_manifest_versions")
    op.drop_table("project_manifest_versions")
