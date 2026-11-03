"""Multi-tenant y roles (Fase 9): ``roles``, ``users.role_id``/``is_instance_admin``, ``sessions.acting_tenant_id``.

Datos: cada tenant recibe sus roles base («Administrador» con todos los permisos y «Usuario» con
``projects.create``). Los ``admin`` pasan a «Administrador» y a admin de instancia (decisión E4); los ``user``, a
«Usuario». El ``downgrade`` devuelve ``admin`` a quien es admin de instancia o tiene ``projects.all``.

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-03
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ALL_PERMISSIONS = ["users.manage", "roles.manage", "audit.read", "templates.manage", "projects.create", "projects.all"]
BUILTIN = {"admin": ("Administrador", ALL_PERMISSIONS), "user": ("Usuario", ["projects.create"])}


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def upgrade() -> None:
    # Sin recrear ``tenants`` (la referencian casi todas las tablas): columna con valor por defecto y después la fecha.
    op.add_column(
        "tenants",
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("'1970-01-01 00:00:00'")),
    )
    op.execute(sa.text("UPDATE tenants SET updated_at = created_at"))

    roles = op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("builtin", sa.String(length=16), nullable=True),
        sa.Column("permissions", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name=op.f("fk_roles_tenant_id_tenants")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roles")),
        sa.UniqueConstraint("tenant_id", "name", name="uq_roles_tenant_name"),
    )
    op.create_index(op.f("ix_roles_tenant_id"), "roles", ["tenant_id"], unique=False)

    conn = op.get_bind()
    tenant_ids = [row[0] for row in conn.execute(sa.text("SELECT id FROM tenants ORDER BY id"))]
    now = _now()
    op.bulk_insert(
        roles,
        [
            {
                "tenant_id": tenant_id,
                "name": name,
                "builtin": key,
                "permissions": permissions,
                "created_at": now,
                "updated_at": now,
            }
            for tenant_id in tenant_ids
            for key, (name, permissions) in BUILTIN.items()
        ],
    )

    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("role_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("is_instance_admin", sa.Boolean(), nullable=False, server_default=sa.false()))
    conn.execute(
        sa.text(
            "UPDATE users SET role_id = (SELECT r.id FROM roles r WHERE r.tenant_id = users.tenant_id "
            "AND r.builtin = users.role), is_instance_admin = (users.role = 'admin')"
        )
    )
    with op.batch_alter_table("users", recreate="always") as batch:
        batch.drop_constraint(op.f("ck_users_role"), type_="check")
        batch.drop_column("role")
        batch.alter_column("role_id", existing_type=sa.Integer(), nullable=False)
        batch.create_foreign_key(op.f("fk_users_role_id_roles"), "roles", ["role_id"], ["id"])
        batch.create_index(op.f("ix_users_role_id"), ["role_id"], unique=False)

    with op.batch_alter_table("sessions") as batch:
        batch.add_column(sa.Column("acting_tenant_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            op.f("fk_sessions_acting_tenant_id_tenants"), "tenants", ["acting_tenant_id"], ["id"], ondelete="SET NULL"
        )


def downgrade() -> None:
    with op.batch_alter_table("sessions") as batch:
        batch.drop_constraint(op.f("fk_sessions_acting_tenant_id_tenants"), type_="foreignkey")
        batch.drop_column("acting_tenant_id")

    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("role", sa.String(length=16), nullable=True))
    conn = op.get_bind()
    for user_id, is_instance_admin, permissions in conn.execute(
        sa.text("SELECT u.id, u.is_instance_admin, r.permissions FROM users u JOIN roles r ON r.id = u.role_id")
    ):
        granted = json.loads(permissions) if isinstance(permissions, str) else permissions
        role = "admin" if is_instance_admin or "projects.all" in (granted or []) else "user"
        conn.execute(sa.text("UPDATE users SET role = :role WHERE id = :id"), {"role": role, "id": user_id})
    with op.batch_alter_table("users", recreate="always") as batch:
        batch.drop_index(op.f("ix_users_role_id"))
        batch.drop_constraint(op.f("fk_users_role_id_roles"), type_="foreignkey")
        batch.drop_column("role_id")
        batch.drop_column("is_instance_admin")
        batch.alter_column("role", existing_type=sa.String(length=16), nullable=False)
        batch.create_check_constraint(op.f("ck_users_role"), "role IN ('admin', 'user')")

    op.drop_index(op.f("ix_roles_tenant_id"), table_name="roles")
    op.drop_table("roles")
    op.drop_column("tenants", "updated_at")
