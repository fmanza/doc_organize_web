"""Frescura del contexto (W4, doc_organize 2.0 F4): ``project_contexts.freshness`` guarda el último resultado de
``check_context_freshness`` (recuentos y unos pocos ejemplos con rutas relativas), que calculan el escaneo y la
construcción en el worker. Nula: aún no se ha comprobado. Aditiva.

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("project_contexts") as batch:
        batch.add_column(sa.Column("freshness", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("project_contexts") as batch:
        batch.drop_column("freshness")
