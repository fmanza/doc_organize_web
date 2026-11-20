"""Versiones y semántica del contexto (W6, doc_organize 2.0 F5 y G4).

- ``projects.context_semantic_threshold``: similitud mínima de la sub-fase semántica (por defecto 0,75, el de la
  librería).
- ``project_contexts``: ``versions_mode`` de la construcción, sus grupos de versiones (``version_groups``: clave,
  miembros con ruta relativa, versiones, vigente y si una persona la confirmó) y las versiones antiguas que quedaron
  fuera con ``current_only`` (``superseded``, rutas relativas, como mucho 500, y ``superseded_count``).

Aditiva; los contextos ya proyectados los rellenan al reconstruir.

Revision ID: 0021
Revises: 0020
Create Date: 2026-11-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("projects") as batch:
        batch.add_column(sa.Column("context_semantic_threshold", sa.Float(), nullable=False, server_default="0.75"))
    with op.batch_alter_table("project_contexts") as batch:
        batch.add_column(sa.Column("versions_mode", sa.String(length=16), nullable=True))
        batch.add_column(sa.Column("version_groups", sa.JSON(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("superseded", sa.JSON(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("superseded_count", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    with op.batch_alter_table("project_contexts") as batch:
        batch.drop_column("superseded_count")
        batch.drop_column("superseded")
        batch.drop_column("version_groups")
        batch.drop_column("versions_mode")
    with op.batch_alter_table("projects") as batch:
        batch.drop_column("context_semantic_threshold")
