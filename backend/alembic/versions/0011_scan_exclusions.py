"""Exclusiones del escaneo (1.4.0, G41): subcarpetas excluidas por carpeta guardada y patrones por ubicación.

Aditiva: columnas JSON con ``[]`` por defecto, así que sin exclusiones ni patrones el escaneo es el de la 1.3.0.

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("scanned_folders") as batch:
        batch.add_column(sa.Column("excluded_subpaths", sa.JSON(), nullable=False, server_default="[]"))
    with op.batch_alter_table("locations") as batch:
        batch.add_column(sa.Column("ignore_patterns", sa.JSON(), nullable=False, server_default="[]"))


def downgrade() -> None:
    with op.batch_alter_table("locations") as batch:
        batch.drop_column("ignore_patterns")
    with op.batch_alter_table("scanned_folders") as batch:
        batch.drop_column("excluded_subpaths")
