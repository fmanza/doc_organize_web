"""Operación ``scan`` (Fase 4) en el propio proceso, con doc_organize sustituido en la capa anticorrupción: una llamada
por carpeta, recuentos sumados, errores guardados sin rutas del contenedor, carpetas marcadas como usadas, cancelación
a mitad conservando lo hecho, documento que agota el tiempo (parada ordenada) y la vista previa de «forzar».

La conversión real con Docling está en ``tests/integration/test_scan_real.py`` (marcada ``integration``)."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.db.models import AuditEntry, Location, Project, Run, RunEvent, ScanError, ScannedFolder, Worker, utcnow
from app.db.session import get_engine
from app.domain.runs.operations import ScanParams
from app.integrations import doc_organize as library
from app.integrations.doc_organize import ScanFailure, ScanOutcome, ScanProgress, ScanRequest
from app.jobs import queue
from app.jobs.context import JobCancelled, JobContext, JobFailed, JobRecycle
from app.jobs.operations import scan as scan_op
from app.jobs.operations.scan import folder_state
from tests.conftest import project_payload

Fake = Callable[..., ScanOutcome]


@pytest.fixture
def project(user_client: TestClient, project_locations: dict[str, Location], migrated: Settings) -> Project:
    (migrated.locations_root / "origen" / "2025" / "b.txt").write_text("otro documento", encoding="utf-8")
    payload = project_payload(project_locations, source_subpaths=["2024", "2025"])
    response = user_client.post("/api/v1/projects", json=payload)
    assert response.status_code == 201, response.text
    with sessionmaker(bind=get_engine(), expire_on_commit=False)() as db:
        loaded = db.get(Project, response.json()["id"])
        assert loaded is not None
        _ = (loaded.source_location, loaded.destination_location)
        db.expunge(loaded)
        return loaded


@pytest.fixture
def ctx(
    user_client: TestClient, project: Project, db: Session, migrated: Settings, tmp_path: Path
) -> Iterator[JobContext]:
    response = user_client.post(f"/api/v1/projects/{project.id}/runs", json={"operation": "scan"})
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


def _outcome(request: ScanRequest, **summary: Any) -> ScanOutcome:
    return ScanOutcome(
        summary={"scanned": 1, "converted": 1, "duration_seconds": 0.5, **summary}, event_schema_version=1
    )


def test_one_call_per_folder_with_summed_counts(
    ctx: JobContext, project: Project, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[ScanRequest] = []
    source = Path(project.source_location.container_path)

    def fake(
        request: ScanRequest, *, on_progress: Callable[[ScanProgress], None], is_cancelled: Callable[[], bool]
    ) -> ScanOutcome:
        calls.append(request)
        folder = request.folders[0]
        on_progress(ScanProgress("conversion", 0, 1, str(folder / "doc.pdf")))
        outcome = _outcome(request)
        if folder.name == "2025":
            outcome.failures = [ScanFailure(str(folder / "roto.pdf"), f"No se pudo abrir {folder}/roto.pdf", 2, False)]
            outcome.warnings = [f"La carpeta {source}/vieja ya no existe"]
        return outcome

    monkeypatch.setattr(library, "run_scan", fake)

    result = scan_op.run(ctx, ScanParams(), project)

    assert [c.folders for c in calls] == [[source / "2024"], [source / "2025"]]
    assert all(not c.force and c.use_ocr for c in calls)
    # Cada carpeta es un ámbito propio: salida y caché separadas (sin esto, 2024/x/a.pdf y 2025/x/a.pdf chocarían).
    project_state = ctx.settings.data_dir / "projects" / str(project.id)
    assert [c.output_subdir for c in calls] == ["2024", "2025"]
    assert [c.state_root for c in calls] == [folder_state(project_state, "2024"), folder_state(project_state, "2025")]
    assert calls[0].state_root != calls[1].state_root and calls[0].state_root.is_relative_to(project_state)
    assert result["scanned"] == 2 and result["converted"] == 2 and result["errors"] == 1
    assert result["folders"] == 2 and result["duration_seconds"] == 1.0 and result["event_schema_version"] == 1
    error = db.scalars(select(ScanError).where(ScanError.run_id == ctx.run_id)).one()
    assert (error.path, error.message, error.retry_count) == (
        "2025/roto.pdf",
        "No se pudo abrir «Origen»/2025/roto.pdf",
        2,
    )
    folders = db.scalars(select(ScannedFolder).where(ScannedFolder.project_id == project.id)).all()
    assert all(f.used and f.last_run_id == ctx.run_id for f in folders)
    logs = [e.data["message"] for e in db.scalars(select(RunEvent).where(RunEvent.type == "log"))]
    assert "La carpeta «Origen»/vieja ya no existe" in logs
    run = db.get(Run, ctx.run_id)
    assert run is not None and run.progress is not None
    assert all(str(source) not in str(e.data) for e in db.scalars(select(RunEvent)))


def test_force_works_folder_by_folder_and_is_audited(
    ctx: JobContext, project: Project, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[ScanRequest] = []

    def fake(request: ScanRequest, **_: Any) -> ScanOutcome:
        calls.append(request)
        return _outcome(request, converted=5)

    monkeypatch.setattr(library, "run_scan", fake)
    monkeypatch.setattr(library, "cached_paths", lambda output, state: [])

    result = scan_op.run(ctx, ScanParams(force=True), project)

    assert len(calls) == 2 and all(c.force and len(c.folders) == 1 for c in calls)
    assert result["converted"] == 10
    assert db.scalars(select(AuditEntry).where(AuditEntry.action == "project.scan_force")).one()


def test_cancel_midway_keeps_what_was_done(
    ctx: JobContext, project: Project, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake(
        request: ScanRequest, *, on_progress: Callable[[ScanProgress], None], is_cancelled: Callable[[], bool]
    ) -> ScanOutcome:
        with sessionmaker(bind=get_engine())() as other:
            other.execute(update(Run).where(Run.id == ctx.run_id).values(cancel_requested=True, cancel_reason="user"))
            other.commit()
        deadline = time.monotonic() + 10
        while not is_cancelled() and time.monotonic() < deadline:  # doc_organize para entre documentos
            time.sleep(0.1)
        outcome = _outcome(request, converted=1)
        outcome.cancelled = True
        outcome.failures = [ScanFailure(str(request.folders[0] / "x.pdf"), "fallo", 1, False)]
        return outcome

    monkeypatch.setattr(library, "run_scan", fake)
    ctx.start_cancel_watch()

    with pytest.raises(JobCancelled) as stopped:
        scan_op.run(ctx, ScanParams(), project)

    assert stopped.value.result is not None and stopped.value.result["converted"] == 1
    assert db.scalar(select(ScanError.path).where(ScanError.run_id == ctx.run_id)) == "2024/x.pdf"
    folders = db.scalars(select(ScannedFolder).where(ScannedFolder.project_id == project.id)).all()
    assert not any(f.used for f in folders)  # ninguna carpeta terminó


def test_document_over_the_time_limit_stops_in_order(
    ctx: JobContext, project: Project, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Un documento que tarda más que el job: el worker pide parar (``timeout``) y la caché de lo hecho se guarda."""

    def fake(
        request: ScanRequest, *, on_progress: Callable[[ScanProgress], None], is_cancelled: Callable[[], bool]
    ) -> ScanOutcome:
        queue.request_stop(db, ctx.run_id, reason="timeout")  # lo que hace el worker al vencer el plazo
        while not is_cancelled():
            time.sleep(0.1)  # el documento lento termina y la librería para antes del siguiente
        outcome = _outcome(request, converted=3)
        outcome.cancelled = True
        return outcome

    monkeypatch.setattr(library, "run_scan", fake)
    ctx.start_cancel_watch()

    with pytest.raises(JobCancelled) as stopped:
        scan_op.run(ctx, ScanParams(), project)

    assert stopped.value.result is not None and stopped.value.result["converted"] == 3
    assert db.scalar(select(Run.cancel_reason).where(Run.id == ctx.run_id)) == "timeout"


def test_missing_folder_is_skipped_with_a_warning(
    ctx: JobContext, project: Project, db: Session, migrated: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    (migrated.locations_root / "origen" / "2025" / "b.txt").unlink()
    (migrated.locations_root / "origen" / "2025").rmdir()
    calls: list[ScanRequest] = []
    monkeypatch.setattr(library, "run_scan", lambda request, **_: calls.append(request) or _outcome(request))

    result = scan_op.run(ctx, ScanParams(), project)

    assert result["folders"] == 1 and len(calls) == 1
    logs = [e.data["message"] for e in db.scalars(select(RunEvent).where(RunEvent.type == "log"))]
    assert any("2025" in m and "ya no existe" in m for m in logs)


def test_worker_without_the_option_fails(ctx: JobContext, project: Project, db: Session) -> None:
    db.add(
        Worker(id="worker-test", queues=["cpu"], version="t", heartbeat_at=utcnow(), capabilities={"gpu_ready": False})
    )
    db.commit()

    with pytest.raises(JobFailed) as failed:
        scan_op.run(ctx, ScanParams(use_gpu=True), project)

    assert failed.value.code == "option_unavailable"


def _caches(project: Project, ctx: JobContext, by_folder: dict[str, list[str]]) -> Callable[[Path, Path], list[str]]:
    state = ctx.settings.data_dir / "projects" / str(project.id)
    states = {folder_state(state, sub): paths for sub, paths in by_folder.items()}
    return lambda output, folder_state_dir: states.get(folder_state_dir, [])


def test_force_preview_counts_cache_and_orphans(
    ctx: JobContext, project: Project, migrated: Settings, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = Path(project.source_location.container_path).resolve()
    conversions = tmp_path / "conversiones"
    (conversions / "2024").mkdir(parents=True)
    (conversions / "2024" / "factura.md").write_text("# Factura", encoding="utf-8")
    cached = {"2024": [str(source / "2024" / "factura.txt"), str(source / "2024" / "borrado.txt")]}
    monkeypatch.setattr(library, "cached_paths", _caches(project, ctx, cached))
    monkeypatch.setattr(library, "conversion_dir", lambda output, state, subdir: conversions / subdir)

    result = scan_op.run(ctx, ScanParams(force=True, dry_run=True), project)

    assert result == {
        "cached": 2,
        "orphaned": 1,
        "excluded": 0,
        "output_files": 1,
        "output_bytes": len("# Factura"),
    }


def test_force_refuses_a_cache_with_documents_outside_its_folder(
    ctx: JobContext, project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    """doc_organize daría a esos documentos una salida plana y podría borrar la de otro: «forzar» no sigue."""
    source = Path(project.source_location.container_path).resolve()
    monkeypatch.setattr(library, "cached_paths", _caches(project, ctx, {"2024": [str(source / "2025" / "b.txt")]}))
    monkeypatch.setattr(library, "run_scan", lambda request, **_: pytest.fail("no debe llegar a doc_organize"))

    with pytest.raises(JobFailed) as failed:
        scan_op.run(ctx, ScanParams(force=True), project)

    assert failed.value.code == "cache_outside_folders"


def test_a_failing_folder_does_not_stop_the_others(
    ctx: JobContext, project: Project, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake(request: ScanRequest, **_: Any) -> ScanOutcome:
        if request.folders[0].name == "2024":
            raise OSError("corte de red")
        return _outcome(request, converted=4)

    monkeypatch.setattr(library, "run_scan", fake)

    with pytest.raises(JobFailed) as failed:
        scan_op.run(ctx, ScanParams(), project)

    assert failed.value.code == "scan_failed"
    assert failed.value.result is not None and failed.value.result["converted"] == 4
    assert failed.value.result["failed_folders"] == 1
    used = {f.subpath: f.used for f in db.scalars(select(ScannedFolder).where(ScannedFolder.project_id == project.id))}
    assert used == {"2024": False, "2025": True}


def test_cancel_between_folders_keeps_the_counts(
    ctx: JobContext, project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake(request: ScanRequest, **_: Any) -> ScanOutcome:
        ctx._cancel.set()  # la cancelación llega justo al terminar la primera carpeta
        return _outcome(request, converted=2)

    monkeypatch.setattr(library, "run_scan", fake)

    with pytest.raises(JobCancelled) as stopped:
        scan_op.run(ctx, ScanParams(), project)

    assert stopped.value.result is not None and stopped.value.result["converted"] == 2


# --- Fase 10: tramos (G38) -----------------------------------------------------------------------------------------


def _save_segment(db: Session, run_id: str, result: dict[str, Any]) -> None:
    """Lo que hace el runner con ``JobRecycle``: guardar el resultado en el run, que sigue ``running``."""
    db.execute(update(Run).where(Run.id == run_id).values(result=result))
    db.commit()


def test_a_long_scan_continues_in_a_new_segment(
    ctx: JobContext, project: Project, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx.settings = ctx.settings.model_copy(
        update={
            "scan_recycle_documents": 3,
            "scan_document_timeout_seconds": 600,
            "scan_io_retries": 4,
            "scan_reuse_hashes": False,
        }
    )
    calls: list[ScanRequest] = []
    outcomes = iter(
        [
            # Tramo 1: «2024» llega al límite a mitad (doc_organize 1.1.0: stopped_reason y remaining).
            ScanOutcome(
                recycled=True,
                summary={"scanned": 10, "new": 10, "converted": 3, "io_errors": 1, "remaining": 7},
            ),
            # Tramo 2: retoma «2024» (el descubrimiento ya contado, también sus io_errors) y escanea «2025».
            ScanOutcome(summary={"scanned": 10, "new": 7, "unchanged": 3, "converted": 7, "io_errors": 1}),
            ScanOutcome(summary={"scanned": 1, "new": 1, "converted": 1, "io_errors": 2}),
        ]
    )

    def fake(request: ScanRequest, **_: Any) -> ScanOutcome:
        calls.append(request)
        return next(outcomes)

    monkeypatch.setattr(library, "run_scan", fake)

    with pytest.raises(JobRecycle) as first:
        scan_op.run(ctx, ScanParams(), project)
    assert first.value.result[scan_op.RESUME] == {"done": [], "partial": "2024", "failed": []}
    assert first.value.result["converted"] == 3
    _save_segment(db, ctx.run_id, first.value.result)

    result = scan_op.run(ctx, ScanParams(), project)

    assert [c.output_subdir for c in calls] == ["2024", "2024", "2025"]
    assert all(c.max_conversions == 3 for c in calls)
    assert {(c.document_timeout_seconds, c.io_retries, c.reuse_hashes) for c in calls} == {(600, 4, False)}
    assert result["segments"] == 2 and scan_op.RESUME not in result
    assert result["converted"] == 11 and result["scanned"] == 11 and result["new"] == 11
    assert result["io_errors"] == 3
    logs = [e.data["message"] for e in db.scalars(select(RunEvent).where(RunEvent.type == "log"))]
    assert any(m.startswith("Tramo 2:") for m in logs)
    assert any("quedan 7 conversiones" in m for m in logs)


def test_a_forced_scan_does_not_empty_the_cache_again_when_resuming(
    ctx: JobContext, project: Project, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[ScanRequest] = []
    outcomes = iter(
        [
            ScanOutcome(recycled=True, summary={"converted": 200, "remaining": 5}),
            ScanOutcome(summary={"converted": 5}),
            ScanOutcome(summary={"converted": 1}),
        ]
    )

    def fake(request: ScanRequest, **_: Any) -> ScanOutcome:
        calls.append(request)
        return next(outcomes)

    monkeypatch.setattr(library, "run_scan", fake)
    monkeypatch.setattr(library, "cached_paths", lambda output, state: [])

    with pytest.raises(JobRecycle) as first:
        scan_op.run(ctx, ScanParams(force=True), project)
    _save_segment(db, ctx.run_id, first.value.result)
    result = scan_op.run(ctx, ScanParams(force=True), project)

    assert [c.force for c in calls] == [True, False, True]
    assert result["converted"] == 206
    assert len(db.scalars(select(AuditEntry).where(AuditEntry.action == "project.scan_force")).all()) == 1


def test_a_finished_folder_is_not_scanned_again(
    ctx: JobContext, project: Project, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[ScanRequest] = []
    monkeypatch.setattr(library, "run_scan", lambda request, **_: calls.append(request) or _outcome(request))
    _save_segment(
        db,
        ctx.run_id,
        {"folders": 2, "force": False, "converted": 4, scan_op.RESUME: {"done": ["2024"], "partial": "2025"}},
    )

    result = scan_op.run(ctx, ScanParams(), project)

    assert [c.output_subdir for c in calls] == ["2025"]
    assert result["converted"] == 5 and result["segments"] == 2


# --- web 1.4.0: exclusiones y patrones (G41) -----------------------------------------------------------------------


def test_exclusions_and_patterns_reach_each_folder(
    ctx: JobContext, project: Project, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[ScanRequest] = []
    monkeypatch.setattr(library, "run_scan", lambda request, **_: calls.append(request) or _outcome(request))
    source = Path(project.source_location.container_path).resolve()

    scan_op.run(ctx, ScanParams(exclusions={"2024": ["fotos", "a/b"]}, ignore_patterns=["~$*", "@eaDir"]), project)

    assert calls[0].exclude_paths == [source / "2024" / "fotos", source / "2024" / "a" / "b"]
    assert calls[1].exclude_paths == []
    assert all(c.ignore_patterns == ["~$*", "@eaDir"] for c in calls)
    logs = [e.data["message"] for e in db.scalars(select(RunEvent).where(RunEvent.type == "log"))]
    assert "«2024»: 2 subcarpetas excluidas." in logs


def test_without_exclusions_the_request_is_the_one_of_1_3_0(
    ctx: JobContext, project: Project, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[ScanRequest] = []

    def fake(request: ScanRequest, **_: Any) -> ScanOutcome:
        calls.append(request)
        return _outcome(request, excluded_cached=0)  # doc_organize 1.3.0 siempre lo da

    monkeypatch.setattr(library, "run_scan", fake)

    result = scan_op.run(ctx, ScanParams(), project)

    assert all(c.exclude_paths == [] and c.ignore_patterns == [] for c in calls)
    assert "excluded_cached" not in result


def test_every_segment_uses_the_copy_made_when_enqueued(
    ctx: JobContext, project: Project, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cambiar las exclusiones con el escaneo en marcha no afecta a sus tramos: no las releen de la BD."""
    calls: list[ScanRequest] = []
    outcomes = iter(
        [
            ScanOutcome(recycled=True, summary={"converted": 3, "remaining": 2, "excluded_cached": 4}),
            ScanOutcome(summary={"converted": 2, "excluded_cached": 4}),
            ScanOutcome(summary={"converted": 1, "excluded_cached": 1}),
        ]
    )

    def fake(request: ScanRequest, **_: Any) -> ScanOutcome:
        calls.append(request)
        return next(outcomes)

    monkeypatch.setattr(library, "run_scan", fake)
    params = ScanParams(exclusions={"2024": ["fotos"]}, ignore_patterns=["~$*"])

    with pytest.raises(JobRecycle) as first:
        scan_op.run(ctx, params, project)
    _save_segment(db, ctx.run_id, first.value.result)
    db.execute(
        update(ScannedFolder)
        .where(ScannedFolder.project_id == project.id, ScannedFolder.subpath == "2024")
        .values(excluded_subpaths=["otra"])
    )
    db.execute(update(Location).where(Location.id == project.source_location_id).values(ignore_patterns=["*.pdf"]))
    db.commit()
    result = scan_op.run(ctx, params, project)

    assert [[p.name for p in c.exclude_paths] for c in calls] == [["fotos"], ["fotos"], []]
    assert all(c.ignore_patterns == ["~$*"] for c in calls)
    # Del descubrimiento: la carpeta retomada no se cuenta dos veces (ni se vuelve a avisar de sus exclusiones).
    assert result["excluded_cached"] == 5
    logs = [e.data["message"] for e in db.scalars(select(RunEvent).where(RunEvent.type == "log"))]
    assert logs.count("«2024»: 1 subcarpeta excluida.") == 1


def test_force_preview_counts_what_exclusions_and_patterns_will_delete(
    ctx: JobContext, project: Project, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = Path(project.source_location.container_path).resolve()
    (source / "2024" / "fotos").mkdir()
    for name in ("fotos/a.jpg", "~$borrador.docx", "notas.txt"):
        (source / "2024" / name).write_text("x", encoding="utf-8")
    cached = {
        "2024": [
            str(source / "2024" / "fotos" / "a.jpg"),  # bajo una exclusión
            str(source / "2024" / "~$borrador.docx"),  # encaja con un patrón
            str(source / "2024" / "notas.txt"),
            str(source / "2024" / "borrado.txt"),  # ya no existe
        ],
        "2025": [str(source / "2025" / "@EADIR" / "miniatura.jpg")],  # carpeta que encaja, sin mayúsculas
    }
    monkeypatch.setattr(library, "cached_paths", _caches(project, ctx, cached))
    monkeypatch.setattr(library, "conversion_dir", lambda output, state, subdir: tmp_path / "nada" / subdir)
    params = ScanParams(force=True, dry_run=True, exclusions={"2024": ["fotos"]}, ignore_patterns=["~$*", "@eaDir"])

    result = scan_op.run(ctx, params, project)

    # Lo excluido se cuenta aparte (también se borra); «orphaned» es solo lo que ya no existe.
    assert (result["cached"], result["excluded"], result["orphaned"]) == (5, 3, 1)


def test_patterns_never_apply_to_the_scanned_folder_itself(
    ctx: JobContext, project: Project, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = Path(project.source_location.container_path).resolve()
    cached = {"2024": [str(source / "2024" / "factura.txt")]}
    monkeypatch.setattr(library, "cached_paths", _caches(project, ctx, cached))
    monkeypatch.setattr(library, "conversion_dir", lambda output, state, subdir: tmp_path / "nada" / subdir)

    result = scan_op.run(ctx, ScanParams(force=True, dry_run=True, ignore_patterns=["2024"]), project)

    assert result["excluded"] == 0
