"""Contexto y taxonomías (Fase 7): ``taxonomy_templates``, ``project_contexts`` y ``context_documents``.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "taxonomy_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=True),
        sa.Column("description", sa.String(length=1024), nullable=True),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_taxonomy_templates_tenant_id_tenants")),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_taxonomy_templates_created_by_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_taxonomy_templates")),
        sa.UniqueConstraint("tenant_id", "name", name="uq_taxonomy_templates_tenant_name"),
    )
    op.create_index(op.f("ix_taxonomy_templates_tenant_id"), "taxonomy_templates", ["tenant_id"], unique=False)
    op.create_table(
        "project_contexts",
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("output_folder_name", sa.String(length=255), nullable=False),
        sa.Column("catalog_kind", sa.String(length=16), nullable=False),
        sa.Column("taxonomy_template_name", sa.String(length=64), nullable=True),
        sa.Column("documents_count", sa.Integer(), nullable=False),
        sa.Column("unclassified_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("collisions_count", sa.Integer(), nullable=False),
        sa.Column("site_built", sa.Boolean(), nullable=False),
        sa.Column("domains", sa.JSON(), nullable=False),
        sa.Column("built_by_run_id", sa.String(length=36), nullable=True),
        sa.Column("built_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_project_contexts_project_id_projects"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["built_by_run_id"],
            ["runs.id"],
            name=op.f("fk_project_contexts_built_by_run_id_runs"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("project_id", name=op.f("pk_project_contexts")),
    )
    op.create_table(
        "context_documents",
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("seq", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("domain_slug", sa.String(length=128), nullable=True),
        sa.Column("title", sa.String(length=1024), nullable=False),
        sa.Column("document_type", sa.String(length=64), nullable=True),
        sa.Column("material_type", sa.String(length=128), nullable=True),
        sa.Column("material_type_name", sa.String(length=256), nullable=True),
        sa.Column("folder", sa.String(length=4096), nullable=False),
        sa.Column("path", sa.String(length=4096), nullable=False),
        sa.Column("organized_path", sa.String(length=4096), nullable=True),
        sa.Column("failed", sa.Boolean(), nullable=False),
        sa.Column("collision", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["project_contexts.project_id"],
            name=op.f("fk_context_documents_project_id_project_contexts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("project_id", "seq", name=op.f("pk_context_documents")),
    )
    op.create_index(
        "ix_context_documents_project_domain", "context_documents", ["project_id", "domain_slug", "seq"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_context_documents_project_domain", table_name="context_documents")
    op.drop_table("context_documents")
    op.drop_table("project_contexts")
    op.drop_index(op.f("ix_taxonomy_templates_tenant_id"), table_name="taxonomy_templates")
    op.drop_table("taxonomy_templates")
