"""Entrega del contexto (W8, doc_organize 2.0.0rc1 F3/F7/D4): Excel del contexto con sus ejes. Plantilla y documentos
sintéticos."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import AuditEntry, Project, User
from app.domain.runs.operations import ExportXlsxParams
from app.jobs.context import JobFailed
from app.jobs.operations import delivery, export
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


# --- sitio sin conexión y paquete para IA ------------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_offline_site_zip_with_its_sha256_without_touching_the_destination(
    run: Any, project: Project, db: Session, user_client: TestClient, admin: User, migrated: Settings
) -> None:
    _setup(user_client, admin)
    _build(run, project, db)
    destination = migrated.locations_root / "salidas" / "Proyecto A"
    before = {p.relative_to(destination): p.stat().st_mtime_ns for p in destination.rglob("*") if p.is_file()}
    ctx, params = run({"operation": "export_site", "llms_txt": True})

    result = delivery.run_site(ctx, params, project)

    (artifact,) = ctx.workdir.glob("export/*-sitio.zip")
    assert result["sha256"] == _sha256(artifact) and result["llms_txt"] is True
    names = set(zipfile.ZipFile(artifact).namelist())
    assert {"sitio/index.html", "sitio/llms.txt", "start_server.py", "VER_SITIO.md"} <= names
    assert not (ctx.workdir / delivery.SITE_BUILD_DIR).exists()  # la copia se borra
    after = {p.relative_to(destination): p.stat().st_mtime_ns for p in destination.rglob("*") if p.is_file()}
    assert after == before  # el destino (y el sitio que sirve la web) no cambia
    entry = db.scalars(select(AuditEntry).where(AuditEntry.action == "project.export_site")).one()
    assert entry.details["sha256"] == result["sha256"]  # type: ignore[index]

    again, params = run({"operation": "export_site", "llms_txt": True})
    assert delivery.run_site(again, params, project)["sha256"] == result["sha256"]  # reproducible


def test_ai_bundle_is_redacted_and_audited(
    run: Any, project: Project, db: Session, user_client: TestClient, admin: User
) -> None:
    _setup(user_client, admin)
    _build(run, project, db)
    ctx, params = run({"operation": "export_ai_bundle", "max_full_chars": 50_000})

    result = delivery.run_ai_bundle(ctx, params, project)

    (artifact,) = ctx.workdir.glob("export/*-ia.zip")
    assert result["sha256"] == _sha256(artifact) and result["documents"] >= 1 and result["redact"] is True
    names = set(zipfile.ZipFile(artifact).namelist())
    assert {"llms.txt", "context.json", "llms-full.txt"} <= names
    assert any(name.startswith("documentos/") and name.endswith(".md") for name in names)
    entry = db.scalars(select(AuditEntry).where(AuditEntry.action == "project.export_ai_bundle")).one()
    assert entry.details["sha256"] == result["sha256"] and entry.details["redact"] is True  # type: ignore[index]


@pytest.mark.posix_paths
def test_ai_bundle_has_no_container_paths(
    run: Any, project: Project, db: Session, user_client: TestClient, admin: User, migrated: Settings
) -> None:
    _setup(user_client, admin)
    _build(run, project, db)
    ctx, params = run({"operation": "export_ai_bundle"})
    delivery.run_ai_bundle(ctx, params, project)

    (artifact,) = ctx.workdir.glob("export/*-ia.zip")
    with zipfile.ZipFile(artifact) as bundle:
        text = " ".join(bundle.read(name).decode("utf-8") for name in bundle.namelist())
    assert str(migrated.locations_root) not in text and RECETA in text


def test_only_an_admin_can_skip_redaction(
    run: Any, project: Project, db: Session, user_client: TestClient, admin: User
) -> None:
    _setup(user_client, admin)
    _build(run, project, db)
    url = f"/api/v1/projects/{project.id}/runs"

    denied = user_client.post(url, json={"operation": "export_ai_bundle", "redact": False})
    allowed = user_client.post(url, json={"operation": "export_ai_bundle"})

    assert denied.status_code == 403 and denied.json()["code"] == "redaction_required"
    assert allowed.status_code == 202


def test_delivery_needs_a_context(project: Project, user_client: TestClient) -> None:
    url = f"/api/v1/projects/{project.id}/runs"
    for body in ({"operation": "export_site"}, {"operation": "export_ai_bundle"}):
        response = user_client.post(url, json=body)
        assert response.status_code == 404 and response.json()["code"] == "context_not_found"


def test_an_offline_site_that_does_not_pass_the_check_is_not_delivered(
    run: Any,
    project: Project,
    db: Session,
    user_client: TestClient,
    admin: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import doc_organize
    from doc_organize import OfflineSiteReport

    _setup(user_client, admin)
    _build(run, project, db)
    monkeypatch.setattr(doc_organize, "check_site_offline", lambda site_dir: OfflineSiteReport(pages=1))
    ctx, params = run({"operation": "export_site"})

    with pytest.raises(JobFailed) as failure:
        delivery.run_site(ctx, params, project)

    assert failure.value.code == "site_offline_invalid"
    assert list(ctx.workdir.glob("export/*.zip")) == []
