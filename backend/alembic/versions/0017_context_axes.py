"""Taxonomía por ejes de doc_organize 2.0 (W2, plan único §I, U3 y U4).

- ``context_document_axis_values``: tabla **genérica** con los valores de todos los ejes de cada documento del contexto
  (``project_id``, ``seq``, ``axis``, ``slug``, ``name``, ``confidence``, ``classified_by``, ``evidence_verified``), con
  índices ``(project_id, axis, slug)`` (filtros y recuentos) y ``(project_id, seq)`` (la clave primaria
  ``(project_id, seq, axis, slug)`` empieza por él). ``context_documents.domain_slug`` y ``material_type`` se quedan
  como columnas derivadas de los ejes organizadores. Los contextos ya proyectados se rellenan con sus ejes de 1.x
  (``domains`` y, con plantilla o manifiesto, ``material_types``), como hace doc_organize al leer un ``context.json`` de
  1.x.
- ``project_contexts.taxonomy_axes`` (JSON): los ejes del contexto (clave, nombre, si admite varios, si organiza y sus
  valores), para pintar filtros sin leer ``context.json``.
- ``taxonomy_templates.markdown`` pasa al formato 2.0 (``migrate_manifest_v1``) y el texto original queda en
  ``markdown_v1``; uno que no se puede migrar se deja tal cual (doc_organize lo seguirá intentando leer).
- Ajustes del proyecto: ``ai_redact_credentials`` (D7, por defecto sí), ``context_versions`` (D8, por defecto
  ``mark``) y ``context_semantic`` (D13, por defecto no).

Bajada: quita lo añadido y devuelve a cada plantilla su ``markdown_v1`` (una plantilla creada después ya en 2.0 se queda
en 2.0: la web 1.x no la leería).

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-19
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FOLDER_AXIS = "domains"  # LEGACY_FOLDER_AXIS_KEY de doc_organize 2.0
SUBFOLDER_AXIS = "material_types"  # LEGACY_SUBFOLDER_AXIS_KEY
UNCLASSIFIED = "sin-clasificar"
BATCH = 1000


def upgrade() -> None:
    op.create_table(
        "context_document_axis_values",
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("axis", sa.String(length=41), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("classified_by", sa.String(length=8), nullable=True),
        sa.Column("evidence_verified", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(
            ["project_id", "seq"],
            ["context_documents.project_id", "context_documents.seq"],
            name=op.f("fk_context_document_axis_values_document"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("project_id", "seq", "axis", "slug", name=op.f("pk_context_document_axis_values")),
    )
    op.create_index(
        "ix_context_document_axis_values_project_axis_slug",
        "context_document_axis_values",
        ["project_id", "axis", "slug"],
    )
    with op.batch_alter_table("project_contexts") as batch:
        batch.add_column(sa.Column("taxonomy_axes", sa.JSON(), nullable=False, server_default="[]"))
    with op.batch_alter_table("taxonomy_templates") as batch:
        batch.add_column(sa.Column("markdown_v1", sa.Text(), nullable=True))
    with op.batch_alter_table("projects") as batch:
        batch.add_column(sa.Column("ai_redact_credentials", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch.add_column(sa.Column("context_versions", sa.String(length=16), nullable=False, server_default="mark"))
        batch.add_column(sa.Column("context_semantic", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.create_check_constraint(
            op.f("ck_projects_context_versions"), "context_versions IN ('all', 'mark', 'current_only')"
        )
    conn = op.get_bind()
    _backfill_axes(conn)
    _migrate_templates(conn)


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE taxonomy_templates SET markdown = markdown_v1 WHERE markdown_v1 IS NOT NULL"))
    with op.batch_alter_table("projects") as batch:
        batch.drop_constraint(op.f("ck_projects_context_versions"), type_="check")
        batch.drop_column("context_semantic")
        batch.drop_column("context_versions")
        batch.drop_column("ai_redact_credentials")
    with op.batch_alter_table("taxonomy_templates") as batch:
        batch.drop_column("markdown_v1")
    with op.batch_alter_table("project_contexts") as batch:
        batch.drop_column("taxonomy_axes")
    op.drop_index("ix_context_document_axis_values_project_axis_slug", table_name="context_document_axis_values")
    op.drop_table("context_document_axis_values")


def _backfill_axes(conn: sa.Connection) -> None:
    """Ejes de 1.x de los contextos ya proyectados (mismo criterio que ``_migrate_context_v1`` de la librería)."""
    contexts = conn.execute(sa.text("SELECT project_id, catalog_kind, domains FROM project_contexts")).mappings().all()
    for context in contexts:
        project_id = context["project_id"]
        two_axes = context["catalog_kind"] in ("template", "manifest")
        domains = context["domains"]
        domains = json.loads(domains) if isinstance(domains, str) else (domains or [])
        names = {d["slug"]: d.get("name") or d["slug"] for d in domains if d.get("slug") != UNCLASSIFIED}
        documents = conn.execute(
            sa.text(
                "SELECT seq, domain_slug, material_type, material_type_name, classified_by, rules_confidence,"
                " ai_confidence, material_type_confidence FROM context_documents WHERE project_id = :p"
            ),
            {"p": project_id},
        ).mappings()
        rows: list[dict[str, Any]] = []
        materials: dict[str, str] = {}
        for doc in documents:
            by = doc["classified_by"] if doc["classified_by"] in ("rules", "ai") else None
            domain = doc["domain_slug"]
            if domain and domain != UNCLASSIFIED:
                confidence = doc["ai_confidence"] if by == "ai" else doc["rules_confidence"]
                rows.append(
                    _value(project_id, doc["seq"], FOLDER_AXIS, domain, names.get(domain, domain), confidence, by)
                )
            material = doc["material_type"]
            if two_axes and domain and material and material != UNCLASSIFIED:
                name = doc["material_type_name"] or material.replace("-", " ").title()
                materials.setdefault(material, name)
                rows.append(
                    _value(project_id, doc["seq"], SUBFOLDER_AXIS, material, name, doc["material_type_confidence"], by)
                )
        for start in range(0, len(rows), BATCH):
            conn.execute(
                sa.text(
                    "INSERT INTO context_document_axis_values (project_id, seq, axis, slug, name, confidence,"
                    " classified_by, evidence_verified) VALUES (:project_id, :seq, :axis, :slug, :name, :confidence,"
                    " :classified_by, NULL)"
                ),
                rows[start : start + BATCH],
            )
        axes: list[dict[str, Any]] = []
        if names:
            axes.append(_axis(FOLDER_AXIS, "Dominios", "folder", names))
        if two_axes and materials:
            axes.append(_axis(SUBFOLDER_AXIS, "Tipos de material", "subfolder", materials))
        conn.execute(
            sa.text("UPDATE project_contexts SET taxonomy_axes = :axes WHERE project_id = :p"),
            {"axes": json.dumps(axes, ensure_ascii=False), "p": project_id},
        )


def _value(
    project_id: int, seq: int, axis: str, slug: str, name: str, confidence: float | None, by: str | None
) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "seq": seq,
        "axis": axis,
        "slug": slug[:128],
        "name": name[:256],
        "confidence": confidence,
        "classified_by": by,
    }


def _axis(key: str, name: str, organizes: str, values: dict[str, str]) -> dict[str, Any]:
    return {
        "key": key,
        "name": name,
        "description": None,
        "multiple": False,
        "organizes": organizes,
        "values": [{"slug": slug, "name": value} for slug, value in values.items()],
    }


def _migrate_templates(conn: sa.Connection) -> None:
    """Plantillas de 1.x → 2.0 con la función de la librería (a través de la capa anticorrupción)."""
    from app.integrations.doc_organize.context import migrate_markdown_v1

    templates = conn.execute(sa.text("SELECT id, markdown FROM taxonomy_templates")).mappings().all()
    for template in templates:
        migrated = migrate_markdown_v1(template["markdown"])
        if migrated is None:
            continue
        conn.execute(
            sa.text("UPDATE taxonomy_templates SET markdown_v1 = markdown, markdown = :m WHERE id = :id"),
            {"m": migrated, "id": template["id"]},
        )
