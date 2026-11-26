"""Retira las columnas heredadas de la 2.x (3.0, ``docs/plan/VERSION_3.0.md``).

- ``context_documents.collision`` y ``project_contexts.collisions_count``: rodeo de G30 para los contextos construidos
  con doc_organize 0.13.0. Antes de borrarlas se dejan en el log (aviso, solo ids) los proyectos con colisiones: hay
  que reconstruir su contexto.
- ``taxonomy_templates.markdown_v1``: el texto 1.x que solo servía para bajar la antigua migración ``0017``.

La bajada recrea las tres columnas con su tipo, nulabilidad y *default* de ``0033`` (al final de la tabla); sus
valores se pierden (``collision`` y ``collisions_count`` vuelven a 0, ``markdown_v1`` a nulo).

Revision ID: 3001
Revises: 0033
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3001"
down_revision: str | None = "0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Hijo de ``alembic`` (nivel INFO en ``alembic.ini``): el aviso sale por la consola de ``alembic upgrade``.
logger = logging.getLogger("alembic.runtime.migration")


def upgrade() -> None:
    project_ids = [
        row[0]
        for row in op.get_bind().execute(
            sa.text("SELECT project_id FROM project_contexts WHERE collisions_count > 0 ORDER BY project_id")
        )
    ]
    if project_ids:
        logger.warning(
            "3001: proyectos con colisiones de nombre en su contexto (doc_organize 0.13.0); reconstruye su contexto: %s",
            ", ".join(str(project_id) for project_id in project_ids),
        )
    with op.batch_alter_table("context_documents") as batch:
        batch.drop_column("collision")
    with op.batch_alter_table("project_contexts") as batch:
        batch.drop_column("collisions_count")
    with op.batch_alter_table("taxonomy_templates") as batch:
        batch.drop_column("markdown_v1")


def downgrade() -> None:
    with op.batch_alter_table("taxonomy_templates") as batch:
        batch.add_column(sa.Column("markdown_v1", sa.Text(), nullable=True))
    # NOT NULL sin default en ``0033``: se añaden con default para rellenar las filas existentes y luego se le quita.
    with op.batch_alter_table("project_contexts") as batch:
        batch.add_column(sa.Column("collisions_count", sa.Integer(), nullable=False, server_default=sa.text("0")))
    with op.batch_alter_table("project_contexts") as batch:
        batch.alter_column("collisions_count", existing_type=sa.Integer(), existing_nullable=False, server_default=None)
    with op.batch_alter_table("context_documents") as batch:
        batch.add_column(sa.Column("collision", sa.Boolean(), nullable=False, server_default=sa.text("0")))
    with op.batch_alter_table("context_documents") as batch:
        batch.alter_column("collision", existing_type=sa.Boolean(), existing_nullable=False, server_default=None)
