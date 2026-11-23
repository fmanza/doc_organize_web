"""Los proyectos borrados sueltan sus ubicaciones (web 2.3.1, opción (a) de C1).

``projects.source_location_id`` y ``destination_location_id`` admiten ``NULL``, solo en proyectos borrados (CHECK
``ck_projects_locations``), y los ya borrados quedan sin ubicaciones: así se puede eliminar una ubicación que solo
usaban proyectos borrados. Qué ubicación usaba cada uno queda en la auditoría (``project.create``).

Bajar solo es posible si ningún proyecto se ha quedado sin ubicación; si no, hay que restaurar la copia de seguridad.

Revision ID: 0029
Revises: 0028
Create Date: 2026-11-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LOCATIONS_CHECK = "status = 'deleted' OR (source_location_id IS NOT NULL AND destination_location_id IS NOT NULL)"


def upgrade() -> None:
    with op.batch_alter_table("projects") as batch:
        batch.alter_column("source_location_id", existing_type=sa.Integer(), nullable=True)
        batch.alter_column("destination_location_id", existing_type=sa.Integer(), nullable=True)
    op.execute("UPDATE projects SET source_location_id = NULL, destination_location_id = NULL WHERE status = 'deleted'")
    with op.batch_alter_table("projects") as batch:
        batch.create_check_constraint(op.f("ck_projects_locations"), _LOCATIONS_CHECK)


def downgrade() -> None:
    orphans = (
        op.get_bind()
        .exec_driver_sql(
            "SELECT count(*) FROM projects WHERE source_location_id IS NULL OR destination_location_id IS NULL"
        )
        .scalar()
    )
    if orphans:
        raise RuntimeError(
            f"{orphans} proyecto(s) borrado(s) ya no tienen ubicación: no se puede bajar de la 0029."
            " Restaura la copia de seguridad previa a la actualización."
        )
    with op.batch_alter_table("projects") as batch:
        batch.drop_constraint(op.f("ck_projects_locations"), type_="check")
        batch.alter_column("source_location_id", existing_type=sa.Integer(), nullable=False)
        batch.alter_column("destination_location_id", existing_type=sa.Integer(), nullable=False)
