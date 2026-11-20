"""Fin de la copia de la configuración de IA de la 1.x (cierre de la 2.0.0): se borra ``ai_settings_v1``.

La ``0016`` la creó para que bajar a la 1.x dejara exactamente las cuatro familias ``litellm_*`` de antes. En la 2.0.0
final el mantenedor decidió no conservarla: bajar desde aquí la recrea **vacía**, y la bajada de la ``0016`` rehace
entonces las cuatro familias desde la familia ``litellm`` de 2.0 (cada una con la URL, la clave de su tarea o la
general, y su modelo), la misma vía que ya seguía cuando la configuración se había cambiado después de subir.

Revision ID: 0024
Revises: 0023
Create Date: 2026-11-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("ai_settings_v1")


def downgrade() -> None:
    # La misma tabla que crea la 0016, vacía: su bajada reconstruye la 1.x desde la configuración de 2.0.
    op.create_table(
        "ai_settings_v1",
        sa.Column("family", sa.String(length=64), nullable=False),
        sa.Column("field", sa.String(length=32), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("ciphertext", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("migrated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("family", "field", name=op.f("pk_ai_settings_v1")),
    )
