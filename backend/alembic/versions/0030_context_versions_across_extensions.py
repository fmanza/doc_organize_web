"""Versiones entre formatos (web 2.5.0, doc_organize 2.5.0 ``build(version_across_extensions=)``).

``projects.context_versions_across_extensions`` (falso: como hasta ahora, solo se agrupan versiones con la misma
extensión) y ``project_contexts.versions_across_extensions`` (lo que hizo cada construcción; nulo en las anteriores).
Aditiva.

Revision ID: 0030
Revises: 0029
Create Date: 2026-11-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("projects") as batch:
        batch.add_column(
            sa.Column("context_versions_across_extensions", sa.Boolean(), nullable=False, server_default=sa.false())
        )
    with op.batch_alter_table("project_contexts") as batch:
        batch.add_column(sa.Column("versions_across_extensions", sa.Boolean(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("project_contexts") as batch:
        batch.drop_column("versions_across_extensions")
    with op.batch_alter_table("projects") as batch:
        batch.drop_column("context_versions_across_extensions")
