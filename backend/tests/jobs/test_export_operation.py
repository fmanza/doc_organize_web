"""Operaciones ``export_zip``, ``export_xlsx`` y ``search_index`` (Fase 5) en el propio proceso, con
``doc_organize.export`` real (no carga Docling): contenido del ZIP y de los Excel sin rutas del contenedor, vista previa
igual al ZIP, cuota, cancelación sin fichero parcial e índice de búsqueda al día."""

from __future__ import annotations

import json
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.db.models import Artifact, Location, Project
from app.db.session import get_engine
from app.domain.projects.service import state_dir
from app.domain.runs.operations import ExportXlsxParams, ExportZipParams, SearchIndexParams
from app.domain.scan.state import CONVERSION_DIR, folder_cache
from app.domain.search.index import search, search_db
from app.integrations import doc_organize as library
from app.jobs import queue
from app.jobs.context import JobCancelled, JobContext, JobFailed
from app.jobs.operations import export, search_index
from tests.api.test_documents import entry, write_cache
from tests.conftest import project_payload


@pytest.fixture
def project(user_client: TestClient, project_locations: dict[str, Location], migrated: Settings) -> Project:
    response = user_client.post(
        "/api/v1/projects", json=project_payload(project_locations, source_subpaths=["2024", "2025"])
    )
    assert response.status_code == 201, response.text
    with sessionmaker(bind=get_engine(), expire_on_commit=False)() as db:
        loaded = db.get(Project, response.json()["id"])
        assert loaded is not None
        _ = (loaded.source_location, loaded.destination_location)
        db.expunge(loaded)
    source = Path(loaded.source_location.container_path)
    state = state_dir(migrated, loaded.id)
    write_cache(
        folder_cache(state, "2024"),
        [
            entry(source / "2024" / "factura.txt"),
            entry(source / "2024" / "roto.pdf", status="error", error=f"Fallo en {source}/2024/roto.pdf"),
        ],
    )
    write_cache(folder_cache(state, "2025"), [entry(source / "2025" / "acta.txt")])
    conversion = Path(loaded.destination_location.container_path) / "Proyecto A" / CONVERSION_DIR
    (conversion / "2024").mkdir(parents=True)
    (conversion / "2025").mkdir()
    (conversion / "2024" / "factura.md").write_text("# Factura\n\nImporte de la luz.", encoding="utf-8")
    (conversion / "2025" / "acta.md").write_text("# Acta\n\nSin luz.", encoding="utf-8")
    return loaded


@pytest.fixture
def ctx(
    user_client: TestClient, project: Project, db: Session, migrated: Settings, tmp_path: Path
) -> Iterator[JobContext]:
    response = user_client.post(f"/api/v1/projects/{project.id}/runs", json={"operation": "export_zip"})
    assert response.status_code == 202, response.text
    assert queue.claim_next(db, "worker-test", ("cpu",)) == response.json()["id"]
    context = JobContext(
        run_id=response.json()["id"],
        settings=migrated,
        session_factory=sessionmaker(bind=get_engine(), expire_on_commit=False),
        workdir=tmp_path / "run",
        created_by=project.created_by,
    )
    yield context
    context.stop_cancel_watch()


def _no_container_paths(text: str, settings: Settings) -> None:
    assert str(settings.locations_root) not in text and str(settings.data_dir) not in text


def test_zip_has_outputs_and_snapshot_without_container_paths(
    ctx: JobContext, project: Project, db: Session, migrated: Settings
) -> None:
    preview = export.run_zip(ctx, ExportZipParams(dry_run=True), project)
    result = export.run_zip(ctx, ExportZipParams(), project)

    assert (preview["file_count"], preview["total_size_bytes"]) == (result["file_count"], result["total_size_bytes"])
    artifact = db.scalars(select(Artifact).where(Artifact.run_id == ctx.run_id)).one()
    assert artifact.name == "Proyecto_A.zip"
    with zipfile.ZipFile(ctx.workdir / artifact.rel_path) as archive:
        names = archive.namelist()
        snapshot = archive.read("cache_export.json").decode("utf-8")
    assert names == ["Conversión/2024/factura.md", "Conversión/2025/acta.md", "cache_export.json"]
    paths = [e["file_path"] for e in json.loads(snapshot)["entries"]]
    assert paths == ["2024/factura.txt", "2024/roto.pdf", "2025/acta.txt"]
    assert "«Origen»/2024/roto.pdf" in snapshot
    _no_container_paths(snapshot, migrated)


def test_zip_preview_writes_nothing(ctx: JobContext, project: Project, db: Session) -> None:
    result = export.run_zip(ctx, ExportZipParams(dry_run=True), project)

    assert result["file_count"] == 3
    assert db.scalars(select(Artifact).where(Artifact.run_id == ctx.run_id)).first() is None
    assert not (ctx.workdir / export.EXPORT_DIR).exists()


def test_zip_larger_than_the_quota_is_refused(
    ctx: JobContext, project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx.settings = ctx.settings.model_copy(update={"user_quota_mb": 1})
    monkeypatch.setattr(library, "zip_preview", lambda request: library.ExportSize(files=1, bytes=5 * 1024 * 1024))

    with pytest.raises(JobFailed) as failed:
        export.run_zip(ctx, ExportZipParams(), project)

    assert failed.value.code == "quota_exceeded"


def test_cancelled_zip_leaves_no_partial_file(
    ctx: JobContext, project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx._cancel.set()

    with pytest.raises(JobCancelled) as cancelled:
        export.run_zip(ctx, ExportZipParams(), project)

    assert cancelled.value.result is not None and cancelled.value.result["file_count"] == 3
    # Se atiende entre la vista previa y la escritura: no se llega a crear nada.
    assert not (ctx.workdir / export.EXPORT_DIR).exists()


def test_zip_cancelled_while_writing_removes_the_partial_file(
    ctx: JobContext, project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"n": 0}

    def cancelled_after_preview() -> bool:
        calls["n"] += 1
        return calls["n"] > 1

    monkeypatch.setattr(type(ctx), "cancelled", property(lambda self: cancelled_after_preview()))

    with pytest.raises(JobCancelled):
        export.run_zip(ctx, ExportZipParams(), project)

    assert list((ctx.workdir / export.EXPORT_DIR).iterdir()) == []


@pytest.mark.parametrize(("kind", "sheets"), [("cache", ["Cache"]), ("errors", ["Estado actual", "Histórico"])])
def test_xlsx_exports_without_container_paths(
    ctx: JobContext, project: Project, db: Session, migrated: Settings, kind: str, sheets: list[str]
) -> None:
    result: dict[str, Any] = export.run_xlsx(ctx, ExportXlsxParams(kind=kind), project)  # type: ignore[arg-type]

    artifact = db.scalars(select(Artifact).where(Artifact.run_id == ctx.run_id)).one()
    workbook = load_workbook(ctx.workdir / artifact.rel_path, read_only=True)
    assert workbook.sheetnames == sheets
    cells = " ".join(str(c) for ws in workbook.worksheets for row in ws.iter_rows(values_only=True) for c in row)
    _no_container_paths(cells, migrated)
    if kind == "cache":
        assert result["rows"] == 3 and "2024/factura.txt" in cells
    else:
        assert result["rows"] == 1 and "«Origen»/2024/roto.pdf" in cells


def test_search_index_is_incremental(ctx: JobContext, project: Project, migrated: Settings) -> None:
    first = search_index.run(ctx, SearchIndexParams(), project)
    second = search_index.run(ctx, SearchIndexParams(), project)
    conversion = Path(project.destination_location.container_path) / "Proyecto A" / CONVERSION_DIR
    (conversion / "2025" / "acta.md").unlink()
    third = search_index.run(ctx, SearchIndexParams(), project)

    assert (first["added"], first["indexed"]) == (2, 2)
    assert (second["added"], second["updated"], second["removed"]) == (0, 0, 0)
    assert (third["removed"], third["indexed"]) == (1, 1)
    hits, total, _ = search(search_db(state_dir(migrated, project.id)), "luz", limit=10, offset=0)
    assert total == 1 and hits[0].output_path == "2024/factura.md"
