"""Idioma de la interfaz por usuario (web 2.6): ``users.language``.

``es`` (español, como hasta ahora) o ``en`` (inglés). Los usuarios existentes quedan en ``es``. Aditiva.

Revision ID: 0031
Revises: 0030
Create Date: 2026-11-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0031"
down_revision: str | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("language", sa.String(length=5), nullable=False, server_default="es"))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("language")
