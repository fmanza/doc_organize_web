"""Escaneo y conversión (Fase 4): ``scanned_folders``, ``scan_errors`` y ``runs.cancel_reason``.

Crea una fila de ``scanned_folders`` por cada carpeta de origen de los proyectos existentes.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-01
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("runs") as batch:
        batch.add_column(sa.Column("cancel_reason", sa.String(length=16), nullable=True))

    folders = op.create_table(
        "scanned_folders",
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("subpath", sa.String(length=4096), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False),
        sa.Column("added_by", sa.Integer(), nullable=True),
        sa.Column("added_at", sa.DateTime(), nullable=False),
        sa.Column("last_scanned_at", sa.DateTime(), nullable=True),
        sa.Column("last_run_id", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_scanned_folders_project_id_projects"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["added_by"], ["users.id"], name=op.f("fk_scanned_folders_added_by_users"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["last_run_id"], ["runs.id"], name=op.f("fk_scanned_folders_last_run_id_runs"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("project_id", "subpath", name=op.f("pk_scanned_folders")),
    )

    op.create_table(
        "scan_errors",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("path", sa.String(length=4096), nullable=False),
        sa.Column("message", sa.String(length=2000), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("capped", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], name=op.f("fk_scan_errors_run_id_runs"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_scan_errors_project_id_projects"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scan_errors")),
    )
    op.create_index(op.f("ix_scan_errors_run_id"), "scan_errors", ["run_id"], unique=False)
    op.create_index("ix_scan_errors_project_run", "scan_errors", ["project_id", "run_id"], unique=False)

    conn = op.get_bind()
    now = datetime.now(UTC).replace(tzinfo=None)
    rows = conn.execute(sa.text("SELECT id, source_subpaths, created_by FROM projects")).all()
    project_table = sa.table("projects", sa.column("source_subpaths", sa.JSON()))
    json_type = project_table.c.source_subpaths.type
    processor = json_type.result_processor(conn.dialect, None)
    seed = []
    for project_id, raw, created_by in rows:
        subpaths = processor(raw) if processor else raw
        seed.extend(
            {"project_id": project_id, "subpath": sub, "used": False, "added_by": created_by, "added_at": now}
            for sub in subpaths or []
        )
    if seed:
        op.bulk_insert(folders, seed)


def downgrade() -> None:
    op.drop_index("ix_scan_errors_project_run", table_name="scan_errors")
    op.drop_index(op.f("ix_scan_errors_run_id"), table_name="scan_errors")
    op.drop_table("scan_errors")
    op.drop_table("scanned_folders")
    with op.batch_alter_table("runs") as batch:
        batch.drop_column("cancel_reason")
