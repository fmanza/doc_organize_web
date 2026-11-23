"""Tema de la interfaz por usuario (web 2.3): ``users.color_scheme``.

``auto`` (el del sistema operativo, como hasta ahora), ``light`` o ``dark``. Los usuarios existentes quedan en
``auto``. Aditiva.

Revision ID: 0028
Revises: 0027
Create Date: 2026-11-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("color_scheme", sa.String(length=8), nullable=False, server_default="auto"))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("color_scheme")
