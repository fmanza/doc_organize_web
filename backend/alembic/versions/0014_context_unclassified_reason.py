"""Motivo de los documentos sin clasificar del contexto (1.6.0, doc_organize 1.6.0 ``UnclassifiedDocument``, G42).

Aditiva: las filas existentes quedan con el motivo nulo hasta la siguiente construcción del contexto, que sustituye la
proyección entera. Autor, descripción, palabras clave, idioma y la propuesta de las reglas de los sin clasificar van en
las columnas que ya añadió ``0013``.

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("context_documents") as batch:
        batch.add_column(sa.Column("unclassified_reason", sa.String(32), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("context_documents") as batch:
        batch.drop_column("unclassified_reason")
