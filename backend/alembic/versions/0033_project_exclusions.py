"""Exclusiones del proyecto (web 2.7, ADR-017): ``projects.excluded_paths``, ``ignore_patterns`` y
``exclude_system_folders``.

Rutas relativas a la ubicación de origen y patrones de nombre que valen para todas las carpetas del proyecto, y el
preset de carpetas de sistema (NAS y Windows). Los proyectos existentes quedan sin exclusiones y sin el preset, para no
cambiar sus resultados sin avisar; el alta de proyectos lo activa. Aditiva.

Revision ID: 0033
Revises: 0032
Create Date: 2026-11-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0033"
down_revision: str | None = "0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("projects") as batch:
        batch.add_column(sa.Column("excluded_paths", sa.JSON(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("ignore_patterns", sa.JSON(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("exclude_system_folders", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table("projects") as batch:
        batch.drop_column("exclude_system_folders")
        batch.drop_column("ignore_patterns")
        batch.drop_column("excluded_paths")
