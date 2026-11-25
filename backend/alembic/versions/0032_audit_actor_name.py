"""Nombre del actor en la auditoría (web 2.7): ``audit_log.actor_name``.

Desde la 2.7 los usuarios se pueden borrar (ADR-016): ``actor_user_id`` pasa a ``NULL`` y la auditoría conservaría la
acción sin su autor. ``actor_name`` guarda el nombre de usuario al registrar el evento; se rellena con el de cada
actor existente. Aditiva.

Revision ID: 0032
Revises: 0031
Create Date: 2026-11-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0032"
down_revision: str | None = "0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("audit_log") as batch:
        batch.add_column(sa.Column("actor_name", sa.String(length=64), nullable=True))
    op.execute(
        "UPDATE audit_log SET actor_name = (SELECT username FROM users WHERE users.id = audit_log.actor_user_id) "
        "WHERE actor_user_id IS NOT NULL"
    )


def downgrade() -> None:
    with op.batch_alter_table("audit_log") as batch:
        batch.drop_column("actor_name")
