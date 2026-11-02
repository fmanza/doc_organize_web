"""Operaciones ``dedup_preview`` y ``dedup_apply`` (Fase 6) en el propio proceso, con ``DeduplicationManager`` real
de doc_organize (no carga Docling) y documentos sintéticos: grupos guardados con rutas relativas, Excel sin rutas del
servidor, modo «nombre parecido» y su tope, y aplicar solo lo confirmado (copiar, mover, solo informe), saltando los
grupos que cambiaron desde la vista previa."""

from __future__ import annotations

import hashlib
import os
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from doc_organize import CacheEntry
from doc_organize.core.models import ConversionStatus, DocumentStatus
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.db.models import Artifact, AuditEntry, DuplicateGroupRow, Location, Project
from app.db.session import get_engine
from app.domain.projects.service import state_dir
from app.domain.runs.operations import DedupApplyParams, DedupChoice, DedupPreviewParams
from app.domain.scan.state import folder_cache
from app.jobs import queue
from app.jobs.context import JobCancelled, JobContext, JobFailed
from app.jobs.operations import dedup
from tests.api.test_documents import write_cache
from tests.conftest import project_payload

#: Documentos sintéticos: (carpeta, nombre, contenido, segundos de antigüedad).
FILES = [
    ("2024", "factura.txt", "factura de enero", 300),
    ("2025", "factura copia.txt", "factura de enero", 100),
    ("2024", "informe_v1.txt", "informe primera versión", 200),
    ("2025", "informe_v2.txt", "informe segunda versión", 50),
    ("2024", "presupuesto obra.txt", "presupuesto A", 10),
    ("2025", "presupuesto obras.txt", "presupuesto B", 20),
]


def _entry(path: Path) -> CacheEntry:
    return CacheEntry(
        file_path=str(path),
        sha256_hash=hashlib.sha256(path.read_bytes()).hexdigest(),
        timestamp=time.time(),
        status=DocumentStatus.NEW,
        conversion_status=ConversionStatus.SUCCESS,
    )


@pytest.fixture
def project(user_client: TestClient, project_locations: dict[str, Location], migrated: Settings) -> Project:
    source = migrated.locations_root / "origen"
    (source / "2024" / "factura.txt").unlink()
    now = time.time()
    for folder, name, content, age in FILES:
        path = source / folder / name
        path.write_text(content, encoding="utf-8")
        os.utime(path, (now - age, now - age))
    response = user_client.post(
        "/api/v1/projects", json=project_payload(project_locations, source_subpaths=["2024", "2025"])
    )
    assert response.status_code == 201, response.text
    with sessionmaker(bind=get_engine(), expire_on_commit=False)() as db:
        loaded = db.get(Project, response.json()["id"])
        assert loaded is not None
        _ = (loaded.source_location, loaded.destination_location)
        db.expunge(loaded)
    state = state_dir(migrated, loaded.id)
    resolved = source.resolve()
    for folder in ("2024", "2025"):
        write_cache(
            folder_cache(state, folder),
            [_entry(resolved / f / n) for f, n, _, _ in FILES if f == folder],
        )
    return loaded


@pytest.fixture
def ctx(
    user_client: TestClient, project: Project, db: Session, migrated: Settings, tmp_path: Path
) -> Iterator[JobContext]:
    response = user_client.post(f"/api/v1/projects/{project.id}/runs", json={"operation": "dedup_preview"})
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


def _groups(db: Session, run_id: str) -> list[DuplicateGroupRow]:
    return list(db.scalars(select(DuplicateGroupRow).where(DuplicateGroupRow.run_id == run_id).order_by("position")))


def _apply(
    ctx: JobContext, db: Session, mode: str, *, dry_run: bool = False, keep: dict[str, str] | None = None
) -> dict:
    groups = _groups(db, ctx.run_id)
    choices = [
        DedupChoice(
            group_id=g.group_id,
            keep=(keep or {}).get(g.reason) or next(f"{m['folder']}/{m['path']}" for m in g.members if m["canonical"]),
        )
        for g in groups
        if g.reason != "fuzzy_name_match"
    ]
    params = DedupApplyParams(groups_run_id=ctx.run_id, mode=mode, groups=choices, dry_run=dry_run)  # type: ignore[arg-type]
    return dedup.run_apply(ctx, params, ctx_project(ctx, db))


def ctx_project(ctx: JobContext, db: Session) -> Project:
    run_project = db.scalars(select(Project)).one()
    _ = (run_project.source_location, run_project.destination_location)
    db.expunge(run_project)
    return run_project


def test_preview_groups_exact_and_versions_across_folders(
    ctx: JobContext, project: Project, db: Session, migrated: Settings
) -> None:
    result = dedup.run_preview(ctx, DedupPreviewParams(), project)

    assert (result["exact_groups"], result["version_groups"], result["fuzzy_groups"]) == (1, 1, 0)
    assert result["documents"] == 6 and result["duplicate_files"] == 2 and result["stale_cache"] == 0
    assert result["reclaimable_bytes"] == len(b"factura de enero")
    exact, version = _groups(db, ctx.run_id)
    assert exact.reason == "exact_duplicate"
    assert [(m["folder"], m["path"], m["canonical"]) for m in exact.members] == [
        ("2024", "factura.txt", True),
        ("2025", "factura copia.txt", False),
    ]
    assert version.reason == "version_conflict" and version.member_count == 2
    artifact = db.scalars(select(Artifact).where(Artifact.run_id == ctx.run_id)).one()
    book = load_workbook(ctx.workdir / artifact.rel_path, read_only=True)
    cells = " ".join(str(c) for row in book.active.iter_rows(values_only=True) for c in row)
    assert "factura copia.txt" in cells and str(migrated.locations_root) not in cells


def test_fuzzy_names_and_their_limit(
    ctx: JobContext, project: Project, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = dedup.run_preview(ctx, DedupPreviewParams(fuzzy_threshold=80), project)

    assert result["fuzzy_groups"] == 1
    fuzzy = [g for g in _groups(db, ctx.run_id) if g.reason == "fuzzy_name_match"][0]
    assert {m["path"] for m in fuzzy.members} == {"presupuesto obra.txt", "presupuesto obras.txt"}
    monkeypatch.setattr(dedup, "MAX_FUZZY_DOCUMENTS", 1)
    with pytest.raises(JobFailed) as failed:
        dedup.run_preview(ctx, DedupPreviewParams(fuzzy_threshold=80), project)
    assert failed.value.code == "fuzzy_too_large"


def test_missing_documents_are_counted_as_stale(ctx: JobContext, project: Project, migrated: Settings) -> None:
    (migrated.locations_root / "origen" / "2025" / "factura copia.txt").unlink()

    result = dedup.run_preview(ctx, DedupPreviewParams(), project)

    assert result["stale_cache"] == 1 and result["exact_groups"] == 0


def test_dry_run_counts_without_touching_files(
    ctx: JobContext, project: Project, db: Session, migrated: Settings
) -> None:
    dedup.run_preview(ctx, DedupPreviewParams(), project)

    result = _apply(ctx, db, "copy", dry_run=True)

    assert (result["groups"], result["files"], result["skipped_changed"]) == (2, 2, 0)
    assert not (migrated.locations_root / "salidas" / "Proyecto A" / "duplicados").exists()


def test_copy_keeps_the_source_and_audits_each_file(
    ctx: JobContext, project: Project, db: Session, migrated: Settings
) -> None:
    dedup.run_preview(ctx, DedupPreviewParams(), project)

    result = _apply(ctx, db, "copy")

    assert (result["processed"], result["failed"], result["groups_done"]) == (2, 0, 2)
    # Relativas a la raíz del origen (G24, doc_organize 0.12.1): sin la ruta absoluta del contenedor.
    duplicates = migrated.locations_root / "salidas" / "Proyecto A" / "duplicados"
    copies = sorted(p.relative_to(duplicates).as_posix() for p in duplicates.rglob("*.txt"))
    assert copies == ["2025/factura copia.txt", "2025/informe_v2.txt"]
    assert (migrated.locations_root / "origen" / "2025" / "factura copia.txt").exists()
    audited = db.scalars(select(AuditEntry).where(AuditEntry.action == "duplicate.copy")).all()
    assert sorted(a.details["path"] for a in audited) == ["2025/factura copia.txt", "2025/informe_v2.txt"]
    assert db.scalars(select(AuditEntry).where(AuditEntry.action == "duplicate.apply")).one()
    report_dir = state_dir(migrated, project.id) / "duplicados"
    assert (report_dir / "DEDUP_REPORT.json").is_file() and (report_dir / "DEDUP_HISTORY.jsonl").is_file()


def test_move_keeps_the_chosen_document(ctx: JobContext, project: Project, db: Session, migrated: Settings) -> None:
    db.execute(update(Location).where(Location.name == "Origen").values(access="rw"))
    db.commit()
    dedup.run_preview(ctx, DedupPreviewParams(), project)

    result = _apply(ctx, db, "move", keep={"exact_duplicate": "2025/factura copia.txt"})

    source = migrated.locations_root / "origen"
    assert result["processed"] == 2
    assert (source / "2025" / "factura copia.txt").exists() and not (source / "2024" / "factura.txt").exists()
    assert (source / "2024" / "informe_v1.txt").exists() and not (source / "2025" / "informe_v2.txt").exists()
    duplicates = migrated.locations_root / "salidas" / "Proyecto A" / "duplicados"
    assert (duplicates / "2024" / "factura.txt").is_file() and (duplicates / "2025" / "informe_v2.txt").is_file()
    assert db.scalars(select(AuditEntry).where(AuditEntry.action == "duplicate.move")).all()


def test_changed_groups_are_skipped(ctx: JobContext, project: Project, db: Session, migrated: Settings) -> None:
    dedup.run_preview(ctx, DedupPreviewParams(), project)
    (migrated.locations_root / "origen" / "2025" / "factura copia.txt").write_text("otra cosa", encoding="utf-8")

    result = _apply(ctx, db, "copy")

    assert (result["skipped_changed"], result["groups_done"], result["processed"]) == (1, 1, 1)


def test_report_only_touches_no_file(ctx: JobContext, project: Project, db: Session, migrated: Settings) -> None:
    dedup.run_preview(ctx, DedupPreviewParams(), project)

    result = _apply(ctx, db, "report_only")

    assert result["processed"] == 2
    assert not (migrated.locations_root / "salidas" / "Proyecto A" / "duplicados").exists()
    assert not db.scalars(select(AuditEntry).where(AuditEntry.action.in_(["duplicate.copy", "duplicate.move"]))).all()


def test_cancel_stops_between_groups(ctx: JobContext, project: Project, db: Session) -> None:
    dedup.run_preview(ctx, DedupPreviewParams(), project)
    ctx._cancel.set()

    with pytest.raises(JobCancelled):
        _apply(ctx, db, "copy")


@pytest.mark.skipif(os.name == "nt", reason="enlaces simbólicos")
def test_a_member_replaced_by_a_link_is_never_followed(
    ctx: JobContext, project: Project, db: Session, migrated: Settings
) -> None:
    dedup.run_preview(ctx, DedupPreviewParams(), project)
    secret = migrated.data_dir / "secreto.txt"
    secret.write_text("factura de enero", encoding="utf-8")
    copy = migrated.locations_root / "origen" / "2025" / "factura copia.txt"
    copy.unlink()
    copy.symlink_to(secret)

    result = _apply(ctx, db, "copy")

    assert result["skipped_changed"] == 1
    copies = [p.name for p in (migrated.locations_root / "salidas" / "Proyecto A" / "duplicados").rglob("*")]
    assert "secreto.txt" not in copies and "factura copia.txt" not in copies


@pytest.mark.skipif(os.name == "nt", reason="enlaces simbólicos")
def test_duplicates_folder_replaced_by_a_link_is_refused(
    ctx: JobContext, project: Project, db: Session, migrated: Settings, tmp_path: Path
) -> None:
    dedup.run_preview(ctx, DedupPreviewParams(), project)
    elsewhere = tmp_path / "otra"
    elsewhere.mkdir()
    (migrated.locations_root / "salidas" / "Proyecto A" / "duplicados").symlink_to(elsewhere)

    with pytest.raises(JobFailed) as failed:
        _apply(ctx, db, "copy")

    assert failed.value.code == "folder_replaced" and list(elsewhere.iterdir()) == []


def test_a_new_preview_replaces_the_groups_of_older_ones(
    user_client: TestClient, ctx: JobContext, project: Project, db: Session, migrated: Settings, tmp_path: Path
) -> None:
    dedup.run_preview(ctx, DedupPreviewParams(), project)
    second = user_client.post(f"/api/v1/projects/{project.id}/runs", json={"operation": "dedup_preview"}).json()["id"]
    other = JobContext(
        run_id=second,
        settings=migrated,
        session_factory=ctx.session_factory,
        workdir=tmp_path / "run2",
        created_by=project.created_by,
    )

    dedup.run_preview(other, DedupPreviewParams(), project)

    assert _groups(db, ctx.run_id) == [] and len(_groups(db, second)) == 2
