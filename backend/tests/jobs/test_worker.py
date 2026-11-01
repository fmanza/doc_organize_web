"""Motor de ejecuciones con subprocesos *spawn* reales (Fase 3): noop, cancelación, timeout, huérfanos y las
operaciones de proyecto sobre carpetas sintéticas (``ProjectHistoryCleaner`` real: no carga Docling)."""

from __future__ import annotations

import time
from collections.abc import Iterator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import AuditEntry, Location, Project, Run, RunEvent, Worker, utcnow
from app.jobs import queue
from app.jobs.worker import JobWorker, purge_workspace
from app.workspace import runs as workspace
from tests.conftest import project_payload


@pytest.fixture
def worker(migrated: Settings) -> Iterator[JobWorker]:
    job_worker = JobWorker(get_settings())
    job_worker.refresh_capabilities = lambda: None  # type: ignore[method-assign]  # sin torch en los tests
    job_worker.register()
    yield job_worker
    job_worker.shutdown()


@pytest.fixture
def project_id(user_client: TestClient, project_locations: dict[str, Location]) -> int:
    response = user_client.post("/api/v1/projects", json=project_payload(project_locations))
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


def _enqueue(client: TestClient, project_id: int, **body: object) -> str:
    response = client.post(f"/api/v1/projects/{project_id}/runs", json=body)
    assert response.status_code == 202, response.text
    return str(response.json()["id"])


def _drive(worker: JobWorker, db: Session, run_id: str, timeout: float = 90) -> Run:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        worker.tick()
        db.expire_all()
        run = db.get(Run, run_id)
        assert run is not None
        if run.status in ("succeeded", "failed", "cancelled") and run_id not in worker.slots:
            return run
        time.sleep(0.2)
    raise AssertionError(f"El run {run_id} no terminó a tiempo")


def _run_and_wait(worker: JobWorker, db: Session, run_id: str) -> Run:
    run = _drive(worker, db, run_id)
    assert run.status == "succeeded", (run.error_code, run.error_message)
    return run


def test_noop_runs_in_subprocess_with_progress_and_artifacts(
    worker: JobWorker, user_client: TestClient, project_id: int, db: Session, migrated: Settings
) -> None:
    run_id = _enqueue(user_client, project_id, operation="noop", steps=3, step_seconds=0)

    run = _run_and_wait(worker, db, run_id)

    assert run.result == {"steps": 3}
    assert run.progress == {"phase": "noop", "processed": 3, "total": 3, "current": "Paso 3"}
    assert {a.name for a in run.artifacts} == {"noop.txt", "run.log"}
    assert (workspace.run_dir(migrated, run_id) / "run.json").is_file()
    types = [e.type for e in db.scalars(select(RunEvent).where(RunEvent.run_id == run_id).order_by(RunEvent.seq))]
    assert types[:2] == ["status", "status"] and types[-2:] == ["status", "end"]
    assert "progress" in types and "artifact" in types
    download = user_client.get(f"/api/v1/runs/{run_id}/artifacts/{run.artifacts[0].id}")
    assert download.status_code == 200


def test_failure_is_reported_with_safe_message(
    worker: JobWorker, user_client: TestClient, project_id: int, db: Session
) -> None:
    run_id = _enqueue(user_client, project_id, operation="noop", steps=3, step_seconds=0, fail_at_step=2)

    run = _drive(worker, db, run_id)

    assert run.status == "failed"
    assert run.error_code == "noop_failed"


def test_cooperative_cancellation(worker: JobWorker, user_client: TestClient, project_id: int, db: Session) -> None:
    run_id = _enqueue(user_client, project_id, operation="noop", steps=50, step_seconds=1)
    for _ in range(50):
        worker.tick()
        db.expire_all()
        if db.get(Run, run_id).status == "running":  # type: ignore[union-attr]
            break
        time.sleep(0.2)
    assert user_client.post(f"/api/v1/runs/{run_id}/cancel").status_code == 202

    run = _drive(worker, db, run_id)

    assert run.status == "cancelled"


def test_timeout_stops_the_job_in_order(
    worker: JobWorker, user_client: TestClient, project_id: int, db: Session
) -> None:
    """Al vencer el plazo el worker pide una parada ordenada (para que un escaneo guarde su caché, G16) y el run
    acaba ``failed``/``timeout`` aunque la operación parase por sí misma."""
    worker.settings = worker.settings.model_copy(update={"job_timeout_seconds": 1})
    run_id = _enqueue(user_client, project_id, operation="noop", steps=100, step_seconds=10)

    run = _drive(worker, db, run_id)

    assert run.status == "failed"
    assert run.error_code == "timeout"
    assert run.cancel_reason == "timeout"
    assert "se guardó lo hecho" in (run.error_message or "")


def test_orphans_are_closed_on_start(migrated: Settings, db: Session, user_client: TestClient, project_id: int) -> None:
    run_id = _enqueue(user_client, project_id, operation="noop")
    db.execute(
        update(Run)
        .where(Run.id == run_id)
        .values(status="running", worker_id="muerto:1", heartbeat_at=utcnow() - timedelta(minutes=10))
    )
    db.commit()

    job_worker = JobWorker(get_settings())
    job_worker.register()
    job_worker.shutdown()

    db.expire_all()
    run = db.get(Run, run_id)
    assert run is not None and run.status == "failed" and run.error_code == "orphaned"


def test_claim_is_exclusive(db: Session, user_client: TestClient, project_id: int) -> None:
    run_id = _enqueue(user_client, project_id, operation="noop")

    assert queue.claim_next(db, "a:1", ("cpu",)) == run_id
    assert queue.claim_next(db, "b:2", ("cpu",)) is None
    assert queue.claim_next(db, "c:3", ("gpu",)) is None


def test_periodic_tasks_are_claimed_once_per_interval(db: Session) -> None:
    assert queue.claim_periodic(db, "tarea", "a:1", timedelta(minutes=5))
    assert not queue.claim_periodic(db, "tarea", "b:2", timedelta(minutes=5))


def test_maintenance_probes_locations_and_purges_workspace(
    worker: JobWorker, user_client: TestClient, project_id: int, db: Session, migrated: Settings
) -> None:
    run_id = _enqueue(user_client, project_id, operation="noop", steps=1, step_seconds=0)
    _run_and_wait(worker, db, run_id)
    db.execute(update(Run).where(Run.id == run_id).values(finished_at=utcnow() - timedelta(days=400)))
    db.execute(update(Location).values(status="unknown"))
    db.commit()

    worker.maintenance_once()

    db.expire_all()
    assert {loc.status for loc in db.scalars(select(Location))} != {"unknown"}
    run = db.get(Run, run_id)
    assert run is not None and run.workspace_purged_at is not None
    assert not workspace.run_dir(migrated, run_id).exists()
    assert purge_workspace(db, migrated) == 0
    assert db.get(Worker, worker.id) is not None


# --- operaciones de proyecto -------------------------------------------------------------------------------------


def _confirm(
    worker: JobWorker, client: TestClient, db: Session, project_id: int, operation: str, **params: object
) -> Run:
    preview = _enqueue(client, project_id, operation=operation, **params)
    _run_and_wait(worker, db, preview)
    real = _enqueue(
        client,
        project_id,
        operation=operation,
        dry_run=False,
        preview_run_id=preview,
        confirm_name="Proyecto A",
        **params,
    )
    return _run_and_wait(worker, db, real)


def test_history_clear_empties_outputs_and_state(
    worker: JobWorker, user_client: TestClient, project_id: int, db: Session, migrated: Settings
) -> None:
    output = migrated.locations_root / "salidas" / "Proyecto A"
    (output / "Conversión").mkdir()
    (output / "Conversión" / "doc.md").write_text("# sintético", encoding="utf-8")
    state = migrated.data_dir / "projects" / str(project_id)
    (state / "cache.db").write_bytes(b"x")

    preview = _enqueue(user_client, project_id, operation="history_clear")
    result = _run_and_wait(worker, db, preview).result
    assert result == {
        "output_files": 1,
        "output_bytes": len("# sintético".encode()),
        "state_files": 1,
        "state_bytes": 1,
    }
    assert (output / "Conversión" / "doc.md").exists()  # la vista previa no toca nada

    _confirm(worker, user_client, db, project_id, "history_clear")

    assert sorted(p.name for p in output.iterdir()) == ["project.json"]
    assert list(state.iterdir()) == []
    assert db.scalar(select(AuditEntry).where(AuditEntry.action == "project.history_clear")) is not None


def test_project_delete_with_outputs(
    worker: JobWorker, user_client: TestClient, project_id: int, db: Session, migrated: Settings
) -> None:
    output = migrated.locations_root / "salidas" / "Proyecto A"
    (output / "a.md").write_text("x", encoding="utf-8")

    _confirm(worker, user_client, db, project_id, "project_delete", delete_outputs=True)

    assert not output.exists()
    assert not (migrated.data_dir / "projects" / str(project_id)).exists()
    db.expire_all()
    assert db.get(Project, project_id).status == "deleted"  # type: ignore[union-attr]
    assert user_client.get(f"/api/v1/projects/{project_id}").status_code == 404
    assert user_client.get("/api/v1/runs", params={"project_id": project_id}).json()["total"] == 2


def test_project_delete_keeping_outputs(
    worker: JobWorker, user_client: TestClient, project_id: int, db: Session, migrated: Settings
) -> None:
    output = migrated.locations_root / "salidas" / "Proyecto A"
    (output / "a.md").write_text("x", encoding="utf-8")

    _confirm(worker, user_client, db, project_id, "project_delete")

    assert (output / "a.md").is_file()


def test_project_move_within_filesystem(
    worker: JobWorker,
    user_client: TestClient,
    project_id: int,
    db: Session,
    migrated: Settings,
    project_locations: dict[str, Location],
) -> None:
    output = migrated.locations_root / "salidas" / "Proyecto A"
    (output / "a.md").write_text("x", encoding="utf-8")
    (migrated.locations_root / "salidas" / "archivo").mkdir()
    params = {
        "destination_location_id": project_locations["destination"].id,
        "destination_parent": "archivo",
        "new_folder": "Proyecto A",
    }

    run = _confirm(worker, user_client, db, project_id, "project_move", **params)

    assert run.result is not None and run.result["same_filesystem"] is True
    assert not output.exists()
    assert (migrated.locations_root / "salidas" / "archivo" / "Proyecto A" / "a.md").is_file()
    assert user_client.get(f"/api/v1/projects/{project_id}").json()["destination_subpath"] == "archivo/Proyecto A"


def test_copy_rolls_back_on_failure(
    user_client: TestClient, project_id: int, migrated: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sqlalchemy.orm import sessionmaker

    from app.db.session import get_engine
    from app.jobs.context import JobContext, JobFailed
    from app.jobs.operations import _files, project_move

    run_id = _enqueue(user_client, project_id, operation="noop")
    ctx = JobContext(
        run_id=run_id,
        settings=migrated,
        session_factory=sessionmaker(bind=get_engine(), expire_on_commit=False),
        workdir=workspace.ensure(migrated, run_id),
        created_by=None,
    )
    source = migrated.locations_root / "salidas" / "Proyecto A"
    (source / "sub").mkdir()
    for name in ("a.md", "sub/b.md"):
        (source / name).write_text(name, encoding="utf-8")
    target = migrated.locations_root / "salidas" / "copia"

    project_move._copy(ctx, source, target, 2)
    assert (target / "sub" / "b.md").read_text(encoding="utf-8") == "sub/b.md"
    assert (source / "a.md").is_file()  # copiar no borra el origen: eso va después del cambio en la BD

    def broken_copy(*_: object, **__: object) -> None:
        raise OSError("disco lleno")

    monkeypatch.setattr(_files.shutil, "copy2", broken_copy)
    again = migrated.locations_root / "salidas" / "otra"
    with pytest.raises(JobFailed):
        project_move._copy(ctx, target, again, 2)
    assert not again.exists()
    assert (target / "a.md").is_file()


def test_swapped_output_folder_is_not_touched(
    worker: JobWorker, user_client: TestClient, project_id: int, db: Session, migrated: Settings
) -> None:
    salidas = migrated.locations_root / "salidas"
    (salidas / "ajena").mkdir()
    (salidas / "ajena" / "no-borrar.txt").write_text("x", encoding="utf-8")
    (salidas / "Proyecto A").rmdir()
    (salidas / "Proyecto A").symlink_to(salidas / "ajena", target_is_directory=True)

    run = _drive(worker, db, _enqueue(user_client, project_id, operation="history_clear"))

    assert (run.status, run.error_code) == ("failed", "folder_replaced")
    assert (salidas / "ajena" / "no-borrar.txt").is_file()


def test_restarted_worker_closes_its_own_runs_even_with_fresh_heartbeat(
    migrated: Settings, db: Session, user_client: TestClient, project_id: int
) -> None:
    job_worker = JobWorker(get_settings())
    run_id = _enqueue(user_client, project_id, operation="noop")
    db.execute(
        update(Run).where(Run.id == run_id).values(status="running", worker_id=job_worker.id, heartbeat_at=utcnow())
    )
    db.commit()

    job_worker.register()
    job_worker.shutdown()

    db.expire_all()
    assert db.get(Run, run_id).error_code == "orphaned"  # type: ignore[union-attr]


def test_critical_phase_is_not_force_cancelled(db: Session, user_client: TestClient, project_id: int) -> None:
    run_id = _enqueue(user_client, project_id, operation="noop")
    db.execute(update(Run).where(Run.id == run_id).values(cancel_requested=True, uninterruptible=True))
    db.commit()

    assert queue.cancel_requested(db, [run_id]) == set()
    db.execute(update(Run).where(Run.id == run_id).values(uninterruptible=False))
    db.commit()
    assert queue.cancel_requested(db, [run_id]) == {run_id}


def test_finish_writes_status_and_end_together(db: Session, user_client: TestClient, project_id: int) -> None:
    run_id = _enqueue(user_client, project_id, operation="noop")
    queue.claim_next(db, "a:1", ("cpu",))

    assert queue.finish(db, run_id, "failed", code="crashed", message="x")
    assert not queue.finish(db, run_id, "failed", code="crashed", message="x")

    types = [e.type for e in db.scalars(select(RunEvent).where(RunEvent.run_id == run_id).order_by(RunEvent.seq))]
    assert types == ["status", "status", "status", "end"]
