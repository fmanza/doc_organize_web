"""Propietario de los ficheros por proyecto (1.5.0, doc_organize 1.5.0 ``ScanOptions.capture_owner``).

Aditiva: ``projects.capture_owner`` a falso para los existentes, así que sus escaneos siguen sin guardar el
propietario.

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("projects") as batch:
        batch.add_column(sa.Column("capture_owner", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table("projects") as batch:
        batch.drop_column("capture_owner")
