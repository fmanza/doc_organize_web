"""Ubicaciones y ajustes administrables (Fase 2): ``locations`` y ``app_settings``.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-31
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "locations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("container_path", sa.String(length=1024), nullable=False),
        sa.Column("display_path", sa.String(length=1024), nullable=True),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("usage", sa.String(length=16), nullable=False),
        sa.Column("access", sa.String(length=8), nullable=False),
        sa.Column("visibility", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("status_reasons", sa.JSON(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("free_bytes", sa.BigInteger(), nullable=True),
        sa.Column("writable", sa.Boolean(), nullable=True),
        sa.Column("probed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("kind IN ('local', 'network')", name=op.f("ck_locations_kind")),
        sa.CheckConstraint("usage IN ('source', 'destination', 'both')", name=op.f("ck_locations_usage")),
        sa.CheckConstraint("access IN ('ro', 'rw')", name=op.f("ck_locations_access")),
        sa.CheckConstraint("status IN ('unknown', 'ok', 'degraded', 'unavailable')", name=op.f("ck_locations_status")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_locations_tenant_id_tenants")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_locations")),
        sa.UniqueConstraint("container_path", name=op.f("uq_locations_container_path")),
        sa.UniqueConstraint("tenant_id", "name", name=op.f("uq_locations_tenant_name")),
    )
    op.create_index(op.f("ix_locations_tenant_id"), "locations", ["tenant_id"], unique=False)
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["users.id"], name=op.f("fk_app_settings_updated_by_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_app_settings")),
    )


def downgrade() -> None:
    op.drop_table("app_settings")
    op.drop_index(op.f("ix_locations_tenant_id"), table_name="locations")
    op.drop_table("locations")
