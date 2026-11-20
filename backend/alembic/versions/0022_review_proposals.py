"""Propuestas del revisor (W7, doc_organize 2.0.0rc1 G6): ``context_review_proposals`` guarda lo que propone el
``ReviewAgent`` para la cola de revisión (acción, ejes, justificación, cita y huella del original), que **no se
aplica** (D14): una persona la acepta (se convierte en decisión) o la descarta. Aditiva.

Revision ID: 0022
Revises: 0021
Create Date: 2026-11-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "context_review_proposals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=True),
        sa.Column("document_key", sa.String(length=4096), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("axes", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("source_sha256", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("decided_by", sa.Integer(), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("decision_id", sa.String(length=64), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'discarded')", name=op.f("ck_context_review_proposals_status")
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_context_review_proposals_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"], name=op.f("fk_context_review_proposals_run_id_runs"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["decided_by"],
            ["users.id"],
            name=op.f("fk_context_review_proposals_decided_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_context_review_proposals")),
    )
    op.create_index(
        "ix_context_review_proposals_project_status", "context_review_proposals", ["project_id", "status", "id"]
    )


def downgrade() -> None:
    op.drop_index("ix_context_review_proposals_project_status", table_name="context_review_proposals")
    op.drop_table("context_review_proposals")
