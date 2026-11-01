"""Escaneo (Fase 4) en la API: carpetas guardadas, lanzar ``scan`` (rol, carpetas, ``force``, opciones contra las
capacidades) y errores de conversión paginados. El worker no corre aquí (ver ``tests/jobs/test_scan.py``)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import AuditEntry, Location, Run, ScanError, ScannedFolder, User, Worker, utcnow
from app.integrations.doc_organize import Capabilities
from tests.conftest import login_as, project_payload


@pytest.fixture
def project(user_client: TestClient, project_locations: dict[str, Location]) -> dict[str, object]:
    response = user_client.post("/api/v1/projects", json=project_payload(project_locations))
    assert response.status_code == 201, response.text
    return dict(response.json())


def _member(client: TestClient, project_id: object, make_user: Callable[..., User], name: str, role: str) -> TestClient:
    other = make_user(name)
    assert (
        client.post(f"/api/v1/projects/{project_id}/members", json={"user_id": other.id, "role": role}).status_code
        == 201
    )
    return login_as(client, name)


def _worker(db: Session, queues: list[str], **capabilities: bool) -> None:
    """Worker vivo con la ficha completa de capacidades (como la publica ``run_probe``)."""
    full = dict.fromkeys(asdict(Capabilities(False, False, False, False, False, False)), False) | capabilities
    db.add(
        Worker(
            id=f"w-{'-'.join(queues)}",
            queues=queues,
            version="test",
            heartbeat_at=utcnow(),
            capabilities=full,
            capabilities_at=utcnow(),
        )
    )
    db.commit()


# --- carpetas guardadas ------------------------------------------------------------------------------------------


def test_project_folders_are_saved_folders(user_client: TestClient, project: dict[str, object]) -> None:
    response = user_client.get(f"/api/v1/projects/{project['id']}/scanned-folders")

    assert response.status_code == 200
    body = response.json()
    assert body["location"]["name"] == "Origen"
    assert [(f["subpath"], f["used"], f["available"]) for f in body["items"]] == [("2024", False, True)]


def test_owner_adds_and_removes_folders(
    user_client: TestClient, project: dict[str, object], db: Session, migrated: Settings
) -> None:
    base = f"/api/v1/projects/{project['id']}/scanned-folders"

    added = user_client.post(base, json={"subpath": "2025"})
    duplicate = user_client.post(base, json={"subpath": "2025"})

    assert added.status_code == 201 and added.json()["subpath"] == "2025"
    assert duplicate.status_code == 409
    assert user_client.get(f"/api/v1/projects/{project['id']}").json()["source_subpaths"] == ["2024", "2025"]
    db.execute(
        ScannedFolder.__table__.update()
        .where(ScannedFolder.project_id == project["id"], ScannedFolder.subpath == "2025")
        .values(used=True)
    )
    db.commit()
    removed = user_client.delete(base, params={"subpath": "2025"})
    assert removed.status_code == 200 and removed.json() == {"subpath": "2025", "used": True}
    assert user_client.delete(base, params={"subpath": "2024"}).json()["code"] == "last_folder"
    assert user_client.delete(base, params={"subpath": "otra"}).status_code == 404
    actions = list(db.scalars(select(AuditEntry.action).where(AuditEntry.action.like("project.scan_folder%"))))
    assert actions == ["project.scan_folder_add", "project.scan_folder_remove"]


def test_nested_folders_are_rejected(user_client: TestClient, project: dict[str, object], migrated: Settings) -> None:
    (migrated.locations_root / "origen" / "2024" / "enero").mkdir()
    base = f"/api/v1/projects/{project['id']}/scanned-folders"

    inner = user_client.post(base, json={"subpath": "2024/enero"})
    outer = user_client.post(base, json={"subpath": ""})
    edit = user_client.patch(f"/api/v1/projects/{project['id']}", json={"source_subpaths": ["2024", "2024/enero"]})

    assert inner.status_code == 422 and inner.json()["code"] == "nested_folders"
    assert outer.json()["code"] == "nested_folders"
    assert edit.json()["code"] == "nested_folders"


def test_only_owner_changes_folders(
    user_client: TestClient, project: dict[str, object], make_user: Callable[..., User]
) -> None:
    editor = _member(user_client, project["id"], make_user, "editora", "editor")
    base = f"/api/v1/projects/{project['id']}/scanned-folders"

    assert editor.get(base).status_code == 200
    assert editor.post(base, json={"subpath": "2025"}).status_code == 403
    assert editor.delete(base, params={"subpath": "2024"}).status_code == 403


def test_folders_cannot_change_with_an_active_run(user_client: TestClient, project: dict[str, object]) -> None:
    assert user_client.post(f"/api/v1/projects/{project['id']}/runs", json={"operation": "scan"}).status_code == 202

    response = user_client.post(f"/api/v1/projects/{project['id']}/scanned-folders", json={"subpath": "2025"})

    assert response.status_code == 409


# --- lanzar el escaneo -------------------------------------------------------------------------------------------


def test_editor_launches_scan_of_all_folders(
    user_client: TestClient, project: dict[str, object], make_user: Callable[..., User], db: Session
) -> None:
    editor = _member(user_client, project["id"], make_user, "editora", "editor")

    response = editor.post(f"/api/v1/projects/{project['id']}/runs", json={"operation": "scan", "folders": ["2024"]})

    assert response.status_code == 202, response.text
    run = response.json()
    assert run["operation"] == "scan" and run["queue"] == "cpu" and run["is_write"] is True
    assert run["params"]["folders"] == []  # todas las carpetas
    assert run["params"]["use_ocr"] is True
    again = editor.post(f"/api/v1/projects/{project['id']}/runs", json={"operation": "scan"})
    assert again.json()["code"] == "write_locked"


def test_scan_rejects_unknown_folders_and_viewers(
    user_client: TestClient, project: dict[str, object], make_user: Callable[..., User]
) -> None:
    viewer = _member(user_client, project["id"], make_user, "lectora", "viewer")
    url = f"/api/v1/projects/{project['id']}/runs"

    assert viewer.post(url, json={"operation": "scan"}).status_code == 403
    unknown = user_client.post(url, json={"operation": "scan", "folders": ["2025"]})
    assert unknown.status_code == 422 and unknown.json()["code"] == "folder_not_saved"


def test_force_requires_owner_all_folders_and_preview(
    user_client: TestClient, project: dict[str, object], make_user: Callable[..., User], db: Session
) -> None:
    url = f"/api/v1/projects/{project['id']}/runs"
    assert (
        user_client.post(f"/api/v1/projects/{project['id']}/scanned-folders", json={"subpath": "2025"}).status_code
        == 201
    )
    editor = _member(user_client, project["id"], make_user, "editora", "editor")

    assert editor.post(url, json={"operation": "scan", "force": True, "dry_run": True}).status_code == 403
    subset = user_client.post(url, json={"operation": "scan", "force": True, "folders": ["2024"]})
    assert subset.json()["code"] == "force_requires_all_folders"
    no_preview = user_client.post(url, json={"operation": "scan", "force": True})
    assert no_preview.json()["code"] == "preview_required"
    preview = user_client.post(url, json={"operation": "scan", "force": True, "dry_run": True})
    assert preview.status_code == 202 and preview.json()["is_write"] is False

    run = db.get(Run, preview.json()["id"])
    assert run is not None
    run.status, run.started_at, run.finished_at = "succeeded", utcnow(), utcnow()
    db.commit()
    real = user_client.post(
        url,
        json={
            "operation": "scan",
            "force": True,
            "folders": ["2024", "2025"],
            "preview_run_id": run.id,
            "confirm_name": "Proyecto A",
        },
    )
    assert real.status_code == 202, real.text
    assert real.json()["params"]["folders"] == []


def test_changing_folders_invalidates_a_force_preview(
    user_client: TestClient, project: dict[str, object], db: Session
) -> None:
    url = f"/api/v1/projects/{project['id']}/runs"
    preview = user_client.post(url, json={"operation": "scan", "force": True, "dry_run": True}).json()
    run = db.get(Run, preview["id"])
    assert run is not None
    run.status, run.started_at, run.finished_at = "succeeded", utcnow(), utcnow()
    db.commit()
    assert (
        user_client.post(f"/api/v1/projects/{project['id']}/scanned-folders", json={"subpath": "2025"}).status_code
        == 201
    )

    real = user_client.post(
        url, json={"operation": "scan", "force": True, "preview_run_id": run.id, "confirm_name": "Proyecto A"}
    )

    assert real.json()["code"] == "preview_required"


def test_options_are_checked_against_worker_capabilities(
    user_client: TestClient, project: dict[str, object], db: Session
) -> None:
    url = f"/api/v1/projects/{project['id']}/runs"

    gpu = user_client.post(url, json={"operation": "scan", "use_gpu": True})
    assert gpu.status_code == 422 and gpu.json()["code"] == "option_unavailable"
    assert "GPU" in gpu.json()["detail"]

    _worker(db, ["cpu"], av_ready=True, picture_description_ready=False)
    _worker(db, ["gpu"], gpu_ready=True)
    assert user_client.post(url, json={"operation": "scan", "use_picture_description": True}).status_code == 422
    accepted = user_client.post(url, json={"operation": "scan", "use_gpu": True, "include_audio_video": False})
    assert accepted.status_code == 202 and accepted.json()["queue"] == "gpu"
    capabilities = user_client.get("/api/v1/instance/capabilities").json()
    assert capabilities["scan_options"] == {
        "use_gpu": True,
        "include_audio_video": True,
        "use_picture_description": False,
    }


# --- errores -----------------------------------------------------------------------------------------------------


def _finished_scan(db: Session, project_id: int, errors: int) -> Run:
    run = Run(
        id=f"00000000-0000-4000-8000-{errors:012d}",
        project_id=project_id,
        operation="scan",
        status="succeeded",
        is_write=True,
        params={"operation": "scan"},
        started_at=utcnow(),
        finished_at=utcnow(),
    )
    db.add(run)
    db.flush()
    db.add_all(
        ScanError(run_id=run.id, project_id=project_id, path=f"2024/doc{i:03d}.pdf", message="No se pudo leer")
        for i in range(errors)
    )
    db.commit()
    return run


def test_scan_errors_are_paginated(
    user_client: TestClient, project: dict[str, object], db: Session, make_user: Callable[..., User]
) -> None:
    project_id = int(str(project["id"]))
    empty = user_client.get(f"/api/v1/projects/{project_id}/scan-errors").json()
    assert empty == {"run": None, "items": [], "total": 0}
    _finished_scan(db, project_id, 3)
    last = _finished_scan(db, project_id, 120)

    page = user_client.get(f"/api/v1/projects/{project_id}/scan-errors", params={"limit": 50, "offset": 100}).json()
    by_run = user_client.get(f"/api/v1/runs/{last.id}/scan-errors", params={"limit": 2}).json()

    assert page["run"]["id"] == last.id and page["total"] == 120 and len(page["items"]) == 20
    assert page["items"][0]["path"] == "2024/doc100.pdf"
    assert [i["path"] for i in by_run["items"]] == ["2024/doc000.pdf", "2024/doc001.pdf"]
    outsider = login_as(user_client, make_user("ajena").username)
    assert outsider.get(f"/api/v1/projects/{project_id}/scan-errors").status_code == 404
    assert outsider.get(f"/api/v1/runs/{last.id}/scan-errors").status_code == 404
