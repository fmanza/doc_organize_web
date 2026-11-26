"""Ejes del contexto con doc_organize 2.0 (W2, U3): ``context_build`` proyecta los valores de todos los ejes en la
tabla genérica ``context_document_axis_values`` y los ejes en ``project_contexts.taxonomy_axes``, con documentos y
plantillas sintéticos."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import ContextDocument, ContextDocumentAxisValue, Project, ProjectContext
from app.jobs.operations import context as operation
from tests.conftest import ADMIN_PASSWORD, login_as
from tests.jobs.test_context_operation import DOMAINS, _finish

#: Plantilla 2.0 sintética con un eje que solo etiqueta (`iva` sale en las facturas de prueba).
AXES_TEMPLATE = """---
schema: 2
title: Obras con ejes
axes:
  - key: domains
    name: Dominios
    organizes: folder
    entries:
      - slug: facturas
        name: Facturas
        keywords: [factura]
      - slug: informes
        name: Informes
  - key: material_types
    name: Tipos de material
    organizes: subfolder
    entries:
      - slug: original
        name: Original
  - key: impuestos
    name: Impuestos
    multiple: true
    entries:
      - slug: iva
        name: IVA
        keywords: [iva]
      - slug: irpf
        name: IRPF
---
Plantilla sintética.
"""


def _values(db: Session, project_id: int) -> dict[tuple[int, str], set[str]]:
    found: dict[tuple[int, str], set[str]] = {}
    rows = db.scalars(select(ContextDocumentAxisValue).where(ContextDocumentAxisValue.project_id == project_id))
    for row in rows:
        found.setdefault((row.seq, row.axis), set()).add(row.slug)
    return found


def test_domain_axis_matches_the_derived_column(run: Any, project: Project, db: Session) -> None:
    ctx, params = run(DOMAINS)

    operation.run_build(ctx, params, project)

    values = _values(db, project.id)
    docs = list(db.scalars(select(ContextDocument).where(ContextDocument.project_id == project.id)))
    for doc in docs:  # domain_slug es la columna derivada del eje que organiza carpetas
        assert values.get((doc.seq, "domains"), set()) == ({doc.domain_slug} if doc.domain_slug else set())
    stored = db.get(ProjectContext, project.id)
    assert stored is not None and [axis["key"] for axis in stored.taxonomy_axes] == ["domains"]
    assert stored.taxonomy_axes[0]["organizes"] == "folder"


def test_tag_axes_are_projected_and_replaced_on_rebuild(
    run: Any, project: Project, db: Session, user_client: TestClient, admin: Any
) -> None:
    admin_client = login_as(user_client, admin.username, ADMIN_PASSWORD)
    saved = admin_client.put("/api/v1/taxonomy-templates/ejes", json={"markdown": AXES_TEMPLATE})
    assert saved.status_code == 201, saved.text
    ctx, params = run(
        {"operation": "context_build", "catalog": "template", "template_name": "ejes", "build_site": False}
    )

    operation.run_build(ctx, params, project)

    stored = db.get(ProjectContext, project.id)
    assert stored is not None
    axes = {axis["key"]: axis for axis in stored.taxonomy_axes}
    assert set(axes) == {"domains", "material_types", "impuestos"}
    assert axes["impuestos"]["multiple"] is True and axes["impuestos"]["organizes"] is None
    assert {v["slug"] for v in axes["impuestos"]["values"]} == {"iva", "irpf"}
    assert "keywords" not in str(stored.taxonomy_axes)
    docs = {d.seq: d for d in db.scalars(select(ContextDocument).where(ContextDocument.project_id == project.id))}
    values = _values(db, project.id)
    tagged = [seq for (seq, axis), slugs in values.items() if axis == "impuestos" and "iva" in slugs]
    assert tagged and all("iva" in docs[seq].title.lower() or docs[seq].path == "factura.txt" for seq in tagged)
    rows = list(db.scalars(select(ContextDocumentAxisValue).where(ContextDocumentAxisValue.axis == "impuestos")))
    assert all(row.classified_by == "rules" and row.name == "IVA" for row in rows)

    _finish(db, ctx)
    ctx2, params2 = run(DOMAINS)
    operation.run_build(ctx2, params2, project)

    assert not any(axis == "impuestos" for _, axis in _values(db, project.id))  # sustituidos, no acumulados


def test_deleting_the_context_deletes_its_axis_values(run: Any, project: Project, db: Session) -> None:
    ctx, params = run(DOMAINS)
    operation.run_build(ctx, params, project)
    assert _values(db, project.id)

    db.execute(ContextDocument.__table__.delete().where(ContextDocument.project_id == project.id))
    db.commit()

    assert _values(db, project.id) == {}  # ON DELETE CASCADE desde context_documents


# --- W3: API de ejes --------------------------------------------------------------------------------------------------


def _build_with_axes(run: Any, project: Project, user_client: TestClient, admin: Any) -> None:
    admin_client = login_as(user_client, admin.username, ADMIN_PASSWORD)
    assert admin_client.put("/api/v1/taxonomy-templates/ejes", json={"markdown": AXES_TEMPLATE}).status_code == 201
    ctx, params = run(
        {"operation": "context_build", "catalog": "template", "template_name": "ejes", "build_site": False}
    )
    operation.run_build(ctx, params, project)


def test_context_lists_axes_with_counts(
    run: Any, project: Project, db: Session, user_client: TestClient, admin: Any
) -> None:
    _build_with_axes(run, project, user_client, admin)

    body = user_client.get(f"/api/v1/projects/{project.id}/context").json()

    axes = {axis["key"]: axis for axis in body["taxonomy_axes"]}
    assert axes["domains"]["organizes"] == "folder" and axes["impuestos"]["multiple"] is True
    counts = {v["slug"]: v["documents"] for v in axes["impuestos"]["values"]}
    stored = db.scalar(
        select(func.count()).select_from(ContextDocumentAxisValue).where(ContextDocumentAxisValue.slug == "iva")
    )
    assert counts == {"iva": stored, "irpf": 0} and stored >= 1
    assert body["ai_provenance"] == []  # sin IA


def test_documents_filter_by_axis(run: Any, project: Project, user_client: TestClient, admin: Any) -> None:
    """O dentro del eje, Y entre ejes; un eje o valor que no existe da lista vacía."""
    _build_with_axes(run, project, user_client, admin)
    url = f"/api/v1/projects/{project.id}/context/documents"

    def total(*filters: str) -> int:
        params: list[tuple[str, str]] = [("domain", "facturas"), *(("axis", f) for f in filters)]
        response = user_client.get(url, params=params)
        assert response.status_code == 200, response.text
        return int(response.json()["total"])

    everything = total()
    with_iva = total("impuestos:iva")
    assert 1 <= with_iva <= everything
    assert total("impuestos:iva", "impuestos:irpf") == with_iva  # O dentro del eje
    assert total("impuestos:iva", "material_types:original") <= with_iva  # Y entre ejes
    assert total("impuestos:irpf") == 0 and total("inexistente:iva") == 0
    page = user_client.get(url, params=[("domain", "facturas"), ("axis", "impuestos:iva")]).json()
    first = page["items"][0]["axes"]
    assert [v["slug"] for v in first["impuestos"]] == ["iva"] and first["impuestos"][0]["classified_by"] == "rules"
    assert first["domains"][0]["slug"] == "facturas" and first["impuestos"][0]["evidence"] is None


def test_axis_filter_is_validated(run: Any, project: Project, user_client: TestClient) -> None:
    """P10: patrón ``clave:slug`` y como mucho 20 valores."""
    ctx, params = run(DOMAINS)
    operation.run_build(ctx, params, project)
    url = f"/api/v1/projects/{project.id}/context/documents"

    for bad in ("sin-dos-puntos", "Mayus:valor", "eje:con espacio", "eje:'; DROP", ":slug"):
        assert user_client.get(url, params={"axis": bad}).status_code == 422, bad
    many = [("axis", f"eje:v{i}") for i in range(21)]
    assert user_client.get(url, params=many).status_code == 422
    assert user_client.get(url, params=many[:20]).status_code == 200


def test_template_reports_implicit_axes_and_ignored_keys(user_client: TestClient, admin: Any) -> None:
    """Aviso de claves ignoradas y ejes implícitos (``inspect_taxonomy_front_matter``) al guardar y leer."""
    admin_client = login_as(user_client, admin.username, ADMIN_PASSWORD)
    legacy = """---
domains:
  - slug: facturas
    name: Facturas
material_types:
  - slug: original
    name: Original
marcos:
  - slug: marco-a
    name: Marco A
notas: texto libre
---
"""
    saved = admin_client.put("/api/v1/taxonomy-templates/implicita", json={"markdown": legacy})

    assert saved.status_code == 201, saved.text
    report = saved.json()["front_matter"]
    assert report["implicit_axes"] == ["marcos"] and report["ignored_keys"] == ["notas"]
    assert "legacy_format" not in report  # 3.0
    assert [(a["key"], a["values"]) for a in report["axes"]] == [("domains", 1), ("material_types", 1), ("marcos", 1)]
    assert user_client.get("/api/v1/taxonomy-templates/implicita").json()["front_matter"] == report
