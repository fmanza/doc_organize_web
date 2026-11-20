"""Entrega del contexto (W8, doc_organize 2.0.0rc1 F3/F7/D4): Excel del contexto con sus ejes. Plantilla y documentos
sintéticos."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Project, User
from app.domain.runs.operations import ExportXlsxParams
from app.jobs.operations import export
from tests.jobs.test_context_review import RECETA, _build, _setup


def _excel(run: Any, project: Project, db: Session, user_client: TestClient, admin: User) -> tuple[Any, Any]:
    _setup(user_client, admin)
    _build(run, project, db)
    ctx, _ = run({"operation": "export_xlsx", "kind": "context_documents"})
    result = export.run_xlsx(ctx, ExportXlsxParams(kind="context_documents"), project)
    (artifact,) = ctx.workdir.glob("export/*-contexto.xlsx")
    assert result["rows"] > 0
    return load_workbook(artifact, read_only=True), result


def test_context_excel_has_every_axis(
    run: Any, project: Project, db: Session, user_client: TestClient, admin: User
) -> None:
    book, _ = _excel(run, project, db, user_client, admin)

    assert book.sheetnames == ["Documentos", "Ejes"]
    header = next(book["Documentos"].iter_rows(values_only=True))
    assert "Impuestos" in header and "Clasificado por" in header  # eje que etiqueta y quién clasificó
    axes = {(row[0], row[3]) for row in list(book["Ejes"].iter_rows(values_only=True))[1:]}
    assert {("domains", "facturas"), ("impuestos", "iva"), ("impuestos", "irpf")} <= axes


@pytest.mark.posix_paths
def test_context_excel_has_relative_paths(
    run: Any, project: Project, db: Session, user_client: TestClient, admin: User, migrated: Settings
) -> None:
    book, _ = _excel(run, project, db, user_client, admin)

    header, *rows = list(book["Documentos"].iter_rows(values_only=True))
    assert RECETA in {row[header.index("Ruta completa")] for row in rows}  # <carpeta>/<ruta>
    cells = " ".join(str(c) for row in rows for c in row if c is not None)
    assert str(migrated.locations_root) not in cells  # sin rutas del contenedor


def test_context_excel_needs_a_context(project: Project, user_client: TestClient) -> None:
    response = user_client.post(
        f"/api/v1/projects/{project.id}/runs", json={"operation": "export_xlsx", "kind": "context_documents"}
    )

    assert response.status_code == 404 and response.json()["code"] == "context_not_found"
