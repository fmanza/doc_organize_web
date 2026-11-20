"""Propuestas del revisor con la clave de doc_organize (W9, 2.0.0rc2: ``ReviewProposal.id``). Aditiva.

Revision ID: 0023
Revises: 0022
Create Date: 2026-11-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("context_review_proposals") as batch:
        batch.add_column(sa.Column("proposal_key", sa.String(length=64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("context_review_proposals") as batch:
        batch.drop_column("proposal_key")
