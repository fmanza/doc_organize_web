"""Proyectos y motor de ejecuciones (Fase 3): ``projects``, ``project_members``, ``runs``, ``run_events``,
``artifacts``, ``workers`` y ``periodic_tasks``.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ACTIVE_WRITE = "is_write AND status IN ('queued', 'running')"


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=1024), nullable=True),
        sa.Column("source_location_id", sa.Integer(), nullable=False),
        sa.Column("source_subpaths", sa.JSON(), nullable=False),
        sa.Column("destination_location_id", sa.Integer(), nullable=False),
        sa.Column("destination_subpath", sa.String(length=4096), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("status IN ('active', 'deleted')", name=op.f("ck_projects_status")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_projects_tenant_id_tenants")),
        sa.ForeignKeyConstraint(
            ["source_location_id"],
            ["locations.id"],
            name=op.f("fk_projects_source_location_id_locations"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["destination_location_id"],
            ["locations.id"],
            name=op.f("fk_projects_destination_location_id_locations"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_projects_created_by_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projects")),
    )
    op.create_index(op.f("ix_projects_tenant_id"), "projects", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_projects_source_location_id"), "projects", ["source_location_id"], unique=False)
    op.create_index(op.f("ix_projects_destination_location_id"), "projects", ["destination_location_id"], unique=False)

    op.create_table(
        "project_members",
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("added_by", sa.Integer(), nullable=True),
        sa.Column("added_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("role IN ('owner', 'editor', 'viewer')", name=op.f("ck_project_members_role")),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_project_members_project_id_projects"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_project_members_user_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["added_by"], ["users.id"], name=op.f("fk_project_members_added_by_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("project_id", "user_id", name=op.f("pk_project_members")),
    )
    op.create_index(op.f("ix_project_members_user_id"), "project_members", ["user_id"], unique=False)

    op.create_table(
        "runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("operation", sa.String(length=32), nullable=False),
        sa.Column("queue", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("is_write", sa.Boolean(), nullable=False),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("progress", sa.JSON(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.String(length=1024), nullable=True),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("uninterruptible", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("worker_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(), nullable=True),
        sa.Column("workspace_purged_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')", name=op.f("ck_runs_status")
        ),
        sa.CheckConstraint("queue IN ('cpu', 'gpu')", name=op.f("ck_runs_queue")),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_runs_project_id_projects"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_runs_created_by_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_runs")),
    )
    op.create_index("ix_runs_claim", "runs", ["status", "queue", "created_at"], unique=False)
    op.create_index("ix_runs_project_created", "runs", ["project_id", "created_at"], unique=False)
    op.create_index(
        "uq_runs_project_write",
        "runs",
        ["project_id"],
        unique=True,
        sqlite_where=sa.text(_ACTIVE_WRITE),
        postgresql_where=sa.text(_ACTIVE_WRITE),
    )

    op.create_table(
        "run_events",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("ts", sa.DateTime(), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], name=op.f("fk_run_events_run_id_runs"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("run_id", "seq", name=op.f("pk_run_events")),
    )

    op.create_table(
        "artifacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("rel_path", sa.String(length=1024), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("kind IN ('log', 'output', 'report')", name=op.f("ck_artifacts_kind")),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], name=op.f("fk_artifacts_run_id_runs"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_artifacts_created_by_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_artifacts")),
    )
    op.create_index(op.f("ix_artifacts_run_id"), "artifacts", ["run_id"], unique=False)

    op.create_table(
        "workers",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("queues", sa.JSON(), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("doc_organize_version", sa.String(length=32), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=True),
        sa.Column("capabilities_at", sa.DateTime(), nullable=True),
        sa.Column("refresh_requested", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workers")),
    )

    op.create_table(
        "periodic_tasks",
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("claimed_by", sa.String(length=128), nullable=True),
        sa.PrimaryKeyConstraint("name", name=op.f("pk_periodic_tasks")),
    )


def downgrade() -> None:
    op.drop_table("periodic_tasks")
    op.drop_table("workers")
    op.drop_index(op.f("ix_artifacts_run_id"), table_name="artifacts")
    op.drop_table("artifacts")
    op.drop_table("run_events")
    op.drop_index("uq_runs_project_write", table_name="runs")
    op.drop_index("ix_runs_project_created", table_name="runs")
    op.drop_index("ix_runs_claim", table_name="runs")
    op.drop_table("runs")
    op.drop_index(op.f("ix_project_members_user_id"), table_name="project_members")
    op.drop_table("project_members")
    op.drop_index(op.f("ix_projects_destination_location_id"), table_name="projects")
    op.drop_index(op.f("ix_projects_source_location_id"), table_name="projects")
    op.drop_index(op.f("ix_projects_tenant_id"), table_name="projects")
    op.drop_table("projects")
