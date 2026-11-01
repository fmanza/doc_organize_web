"""Ejecuciones desde la API (Fase 3): encolar, bloqueo de escritura, vista previa, cancelación, SSE y artefactos.

Aquí no hay worker: los runs se quedan en cola o se cierran a mano en la BD. El worker real se prueba en
``tests/jobs``.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Artifact, Location, Run, User, Worker, utcnow
from app.domain.runs import events
from app.workspace import runs as workspace
from tests.conftest import ADMIN_PASSWORD, login_as, project_payload


@pytest.fixture
def project_id(user_client: TestClient, project_locations: dict[str, Location]) -> int:
    response = user_client.post("/api/v1/projects", json=project_payload(project_locations))
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


def _enqueue(client: TestClient, project_id: int, **body: object) -> dict[str, object]:
    response = client.post(f"/api/v1/projects/{project_id}/runs", json=body)
    assert response.status_code == 202, response.text
    result: dict[str, object] = response.json()
    return result


def _succeed(db: Session, run_id: object, minutes_ago: int = 0) -> None:
    finished = utcnow() - timedelta(minutes=minutes_ago)
    db.execute(update(Run).where(Run.id == run_id).values(status="succeeded", finished_at=finished))
    db.commit()


def _sse(text: str) -> list[tuple[str, str]]:
    """``(id, event)`` de cada evento de un flujo SSE."""
    result = []
    for block in text.split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line and not line.startswith(":"))
        if "event" in fields:
            result.append((fields["id"], fields["event"]))
    return result


def test_enqueue_noop_returns_202_queued(user_client: TestClient, project_id: int) -> None:
    run = _enqueue(user_client, project_id, operation="noop", steps=2, step_seconds=0)

    assert run["status"] == "queued"
    assert run["queue"] == "cpu"
    assert run["is_write"] is False
    assert run["can_cancel"] is True
    assert run["project_name"] == "Proyecto A"


def test_invalid_params_give_422(user_client: TestClient, project_id: int) -> None:
    response = user_client.post(f"/api/v1/projects/{project_id}/runs", json={"operation": "noop", "steps": 0})

    assert response.status_code == 422


def test_destructive_run_needs_preview_and_name(user_client: TestClient, project_id: int, db: Session) -> None:
    real = {"operation": "history_clear", "dry_run": False}
    response = user_client.post(f"/api/v1/projects/{project_id}/runs", json=real)
    assert response.status_code == 409
    assert response.json()["code"] == "preview_required"

    preview = _enqueue(user_client, project_id, operation="history_clear")
    assert preview["is_write"] is False
    bad_name = {**real, "preview_run_id": preview["id"], "confirm_name": "otro"}
    assert user_client.post(f"/api/v1/projects/{project_id}/runs", json=bad_name).json()["code"] == "preview_required"
    pending = {**real, "preview_run_id": preview["id"], "confirm_name": "Proyecto A"}
    assert user_client.post(f"/api/v1/projects/{project_id}/runs", json=pending).status_code == 409  # sin terminar

    _succeed(db, preview["id"])
    run = _enqueue(user_client, project_id, **pending)
    assert run["is_write"] is True


def test_preview_expires(user_client: TestClient, project_id: int, db: Session) -> None:
    preview = _enqueue(user_client, project_id, operation="project_delete")
    _succeed(db, preview["id"], minutes_ago=20)
    body = {
        "operation": "project_delete",
        "dry_run": False,
        "preview_run_id": preview["id"],
        "confirm_name": "Proyecto A",
    }

    response = user_client.post(f"/api/v1/projects/{project_id}/runs", json=body)

    assert response.status_code == 409
    assert "caducado" in response.json()["detail"]


def test_preview_of_other_params_is_rejected(user_client: TestClient, project_id: int, db: Session) -> None:
    preview = _enqueue(user_client, project_id, operation="project_delete", delete_outputs=False)
    _succeed(db, preview["id"])
    body = {
        "operation": "project_delete",
        "dry_run": False,
        "delete_outputs": True,
        "preview_run_id": preview["id"],
        "confirm_name": "Proyecto A",
    }

    assert user_client.post(f"/api/v1/projects/{project_id}/runs", json=body).status_code == 409


def test_one_write_per_project(user_client: TestClient, project_id: int, db: Session) -> None:
    previews = [_enqueue(user_client, project_id, operation="history_clear") for _ in range(2)]
    for preview in previews:
        _succeed(db, preview["id"])
    _enqueue(
        user_client,
        project_id,
        operation="history_clear",
        dry_run=False,
        preview_run_id=previews[1]["id"],
        confirm_name="Proyecto A",
    )

    again = user_client.post(
        f"/api/v1/projects/{project_id}/runs",
        json={
            "operation": "history_clear",
            "dry_run": False,
            "preview_run_id": previews[1]["id"],
            "confirm_name": "Proyecto A",
        },
    )

    # Con una escritura en cola ninguna vista previa vale (el proyecto va a cambiar); el índice lo cubre en BD.
    assert again.status_code == 409
    fresh = _enqueue(user_client, project_id, operation="history_clear")
    _succeed(db, fresh["id"])
    locked = user_client.post(
        f"/api/v1/projects/{project_id}/runs",
        json={
            "operation": "history_clear",
            "dry_run": False,
            "preview_run_id": fresh["id"],
            "confirm_name": "Proyecto A",
        },
    )
    assert locked.json()["code"] == "preview_required"


def test_move_destination_is_validated(
    user_client: TestClient, project_id: int, project_locations: dict[str, Location]
) -> None:
    dest = project_locations["destination"].id
    same = {"operation": "project_move", "destination_location_id": dest, "new_folder": "Proyecto A"}
    inside = {**same, "destination_parent": "Proyecto A", "new_folder": "sub"}
    readonly = {**same, "destination_location_id": project_locations["source"].id}
    escape = {**same, "destination_parent": "../x", "new_folder": "B"}

    for body in (same, inside, readonly, escape):
        assert user_client.post(f"/api/v1/projects/{project_id}/runs", json=body).status_code == 400, body
    ok = _enqueue(user_client, project_id, operation="project_move", destination_location_id=dest, new_folder="B")
    assert ok["params"]["destination_parent"] == ""


def test_cancel_queued_run_and_stream_events(user_client: TestClient, project_id: int) -> None:
    run = _enqueue(user_client, project_id, operation="noop")

    cancelled = user_client.post(f"/api/v1/runs/{run['id']}/cancel")
    assert cancelled.status_code == 202
    assert cancelled.json()["status"] == "cancelled"
    assert user_client.post(f"/api/v1/runs/{run['id']}/cancel").status_code == 409

    stream = user_client.get(f"/api/v1/runs/{run['id']}/events")
    assert stream.status_code == 200
    assert stream.headers["content-type"].startswith("text/event-stream")
    assert _sse(stream.text) == [("1", "status"), ("2", "status"), ("3", "end")]

    resumed = user_client.get(f"/api/v1/runs/{run['id']}/events", headers={"Last-Event-ID": "2"})
    assert _sse(resumed.text) == [("3", "end")]


def test_viewer_cannot_cancel_others_run(user_client: TestClient, project_id: int, make_user: object) -> None:
    bea = make_user("bea")  # type: ignore[operator]
    user_client.post(f"/api/v1/projects/{project_id}/members", json={"user_id": bea.id, "role": "viewer"})
    run = _enqueue(user_client, project_id, operation="noop")
    viewer = login_as(user_client, "bea")

    detail = viewer.get(f"/api/v1/runs/{run['id']}").json()

    assert detail["can_cancel"] is False
    assert viewer.post(f"/api/v1/runs/{run['id']}/cancel").status_code == 403


def test_runs_of_other_projects_are_invisible(user_client: TestClient, project_id: int, make_user: object) -> None:
    run = _enqueue(user_client, project_id, operation="noop")
    make_user("intrusa")  # type: ignore[operator]
    other = login_as(user_client, "intrusa")

    assert other.get("/api/v1/runs").json()["total"] == 0
    for path in (
        f"/api/v1/runs/{run['id']}",
        f"/api/v1/runs/{run['id']}/events",
        f"/api/v1/runs/{run['id']}/artifacts/1",
    ):
        assert other.get(path).status_code == 404, path
    assert other.post(f"/api/v1/runs/{run['id']}/cancel").status_code == 404
    assert other.get("/api/v1/runs/no-es-un-uuid").status_code == 404


def test_history_lists_runs_newest_first_with_filters(user_client: TestClient, project_id: int) -> None:
    first = _enqueue(user_client, project_id, operation="noop")
    second = _enqueue(user_client, project_id, operation="history_clear")
    user_client.post(f"/api/v1/runs/{first['id']}/cancel")

    page = user_client.get("/api/v1/runs", params={"project_id": project_id}).json()
    cancelled = user_client.get("/api/v1/runs", params={"status": "cancelled"}).json()

    assert [r["id"] for r in page["items"]] == [second["id"], first["id"]]
    assert [r["id"] for r in cancelled["items"]] == [first["id"]]
    project = user_client.get(f"/api/v1/projects/{project_id}").json()
    assert project["last_run"]["id"] == second["id"]
    assert project["active_run"] is True


def test_artifact_download_is_attachment_and_confined(
    user_client: TestClient, project_id: int, db: Session, migrated: Settings
) -> None:
    run = _enqueue(user_client, project_id, operation="noop")
    base = workspace.ensure(migrated, str(run["id"]))
    (base / "outputs" / "informe.html").write_text("<script>alert(1)</script>", encoding="utf-8")
    (migrated.workspace_dir / "secreto.txt").write_text("no", encoding="utf-8")
    good = Artifact(
        run_id=run["id"], name="informe.html", kind="output", rel_path="outputs/informe.html", content_type="text/html"
    )
    evil = Artifact(run_id=run["id"], name="x", kind="output", rel_path="../../secreto.txt", content_type="text/plain")
    db.add_all([good, evil])
    db.commit()

    response = user_client.get(f"/api/v1/runs/{run['id']}/artifacts/{good.id}")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.headers["content-disposition"].startswith("attachment")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert user_client.get(f"/api/v1/runs/{run['id']}/artifacts/{evil.id}").status_code == 404

    db.execute(update(Run).where(Run.id == run["id"]).values(workspace_purged_at=utcnow()))
    db.commit()
    assert user_client.get(f"/api/v1/runs/{run['id']}/artifacts/{good.id}").status_code == 410


def test_quota_blocks_runs_that_produce_artifacts(
    user_client: TestClient, project_id: int, db: Session, user: User, admin: User
) -> None:
    run = _enqueue(user_client, project_id, operation="noop")
    db.add(
        Artifact(
            run_id=run["id"],
            name="g",
            kind="output",
            rel_path="outputs/g",
            size_bytes=2 * 1024 * 1024,
            content_type="text/plain",
            created_by=user.id,
        )
    )
    db.commit()
    login_as(user_client, admin.username, ADMIN_PASSWORD).patch(
        "/api/v1/admin/settings", json={"values": {"user_quota_mb": 1}}
    )

    response = user_client.post(f"/api/v1/projects/{project_id}/runs", json={"operation": "noop"})

    assert response.status_code == 409
    assert response.json()["code"] == "quota_exceeded"


def test_events_are_appended_in_order(db: Session, user_client: TestClient, project_id: int) -> None:
    run = _enqueue(user_client, project_id, operation="noop")
    events.append(db, str(run["id"]), "progress", {"phase": "noop", "processed": 1, "total": 2})

    listed = events.after(db, str(run["id"]), 0)

    assert [(e.seq, e.type) for e in listed] == [(1, "status"), (2, "progress")]
    assert listed[1].data["schema_version"] == 1


def test_health_and_capabilities_reflect_workers(
    client: TestClient, user_client: TestClient, db: Session, admin_client: TestClient
) -> None:
    assert client.get("/api/health").json()["worker"] == "none"
    assert user_client.get("/api/v1/instance/capabilities").json()["status"] == "no_worker"

    db.add(Worker(id="w:1", queues=["cpu"], version="t", heartbeat_at=utcnow()))
    db.commit()
    assert client.get("/api/health").json()["worker"] == "ok"
    assert user_client.get("/api/v1/instance/capabilities").json()["status"] == "pending"
    assert admin_client.post("/api/v1/admin/capabilities/refresh").status_code == 202
    db.expire_all()
    assert db.get(Worker, "w:1").refresh_requested is True  # type: ignore[union-attr]
    workers = admin_client.get("/api/v1/admin/workers").json()["items"]
    assert workers[0]["alive"] is True

    db.execute(update(Worker).values(heartbeat_at=utcnow() - timedelta(hours=1), capabilities={"gpu_active": False}))
    db.commit()
    assert client.get("/api/health").json()["worker"] == "stale"


def test_active_runs_per_user_are_capped(user_client: TestClient, project_id: int) -> None:
    for _ in range(5):
        _enqueue(user_client, project_id, operation="noop")

    response = user_client.post(f"/api/v1/projects/{project_id}/runs", json={"operation": "noop"})

    assert response.status_code == 409
    assert response.json()["code"] == "too_many_runs"


def test_user_lookup_needs_two_characters(user_client: TestClient) -> None:
    assert user_client.get("/api/v1/users/lookup", params={"q": "a"}).status_code == 422


def test_write_index_allows_one_active_write_per_project(db: Session, project_id: int) -> None:
    import uuid

    from sqlalchemy.exc import IntegrityError

    db.add(Run(id=str(uuid.uuid4()), project_id=project_id, operation="history_clear", is_write=True, params={}))
    db.commit()
    db.add(Run(id=str(uuid.uuid4()), project_id=project_id, operation="project_delete", is_write=True, params={}))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
