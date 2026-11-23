"""Duplicados por contenido (web 2.2, doc_organize 2.2): similitudes de cada grupo en ``duplicate_groups``.

``similarity`` (semántica), ``lexical_similarity`` (de texto) y ``contained`` (un miembro contenido en otro) solo los
rellenan los grupos por contenido (``same_content``, ``semantic_content_match``); los demás quedan a NULL y false.
Aditiva.

Revision ID: 0027
Revises: 0026
Create Date: 2026-11-22
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("duplicate_groups") as batch:
        batch.add_column(sa.Column("similarity", sa.Float(), nullable=True))
        batch.add_column(sa.Column("lexical_similarity", sa.Float(), nullable=True))
        batch.add_column(sa.Column("contained", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table("duplicate_groups") as batch:
        batch.drop_column("contained")
        batch.drop_column("lexical_similarity")
        batch.drop_column("similarity")
