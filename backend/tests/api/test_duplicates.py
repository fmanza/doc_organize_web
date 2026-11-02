"""Duplicados (Fase 6) en la API: lanzar la vista previa y aplicar (roles por modo, vista previa vigente, grupos y
documento a conservar, origen de solo lectura, doble vista previa al aplicar), grupos paginados y última aplicación.
El trabajo del worker está en ``tests/jobs/test_dedup_operation.py``."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.db.models import DuplicateGroupRow, Location, Run, User, utcnow
from tests.conftest import login_as, project_payload

GROUP = "11111111-2222-4333-8444-555555555555"
MEMBERS = [
    {"folder": "2024", "path": "a.pdf", "size_bytes": 10, "modified_time": 1.0, "sha256": "0" * 64, "canonical": True},
    {
        "folder": "2025",
        "path": "a copia.pdf",
        "size_bytes": 10,
        "modified_time": 2.0,
        "sha256": "0" * 64,
        "canonical": False,
    },
]


@pytest.fixture
def project(user_client: TestClient, project_locations: dict[str, Location]) -> dict[str, object]:
    response = user_client.post(
        "/api/v1/projects", json=project_payload(project_locations, source_subpaths=["2024", "2025"])
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


def _finished_preview(client: TestClient, db: Session, project_id: object, *, age: timedelta = timedelta()) -> str:
    """Vista previa terminada con un grupo exacto (como la deja el worker)."""
    run_id = str(client.post(f"/api/v1/projects/{project_id}/runs", json={"operation": "dedup_preview"}).json()["id"])
    finished = utcnow() - age
    db.execute(
        update(Run).where(Run.id == run_id).values(status="succeeded", started_at=finished, finished_at=finished)
    )
    db.add(
        DuplicateGroupRow(
            run_id=run_id, group_id=GROUP, reason="exact_duplicate", position=0, member_count=2, members=MEMBERS
        )
    )
    db.commit()
    return run_id


def _member(client: TestClient, project_id: object, make_user: Callable[..., User], name: str, role: str) -> TestClient:
    other = make_user(name)
    assert (
        client.post(f"/api/v1/projects/{project_id}/members", json={"user_id": other.id, "role": role}).status_code
        == 201
    )
    return login_as(client, name)


def _apply(groups_run_id: str, mode: str = "copy", **extra: object) -> dict[str, object]:
    return {
        "operation": "dedup_apply",
        "groups_run_id": groups_run_id,
        "mode": mode,
        "groups": [{"group_id": GROUP, "keep": "2025/a copia.pdf"}],
        **extra,
    }


def test_preview_is_for_editors(
    user_client: TestClient, project: dict[str, object], make_user: Callable[..., User]
) -> None:
    viewer = _member(user_client, project["id"], make_user, "lectora", "viewer")
    editor = _member(user_client, project["id"], make_user, "editora", "editor")
    runs = f"/api/v1/projects/{project['id']}/runs"

    assert viewer.post(runs, json={"operation": "dedup_preview"}).status_code == 403
    assert editor.post(runs, json={"operation": "dedup_preview", "fuzzy_threshold": 85}).status_code == 202
    assert editor.post(runs, json={"operation": "dedup_preview", "fuzzy_threshold": 20}).status_code == 422


def test_apply_checks_preview_groups_and_keep(user_client: TestClient, project: dict[str, object], db: Session) -> None:
    runs = f"/api/v1/projects/{project['id']}/runs"
    preview = _finished_preview(user_client, db, project["id"])
    old = _finished_preview(user_client, db, project["id"], age=timedelta(hours=2))

    ok = user_client.post(runs, json=_apply(preview))
    no_preview = user_client.post(runs, json=_apply("00000000-0000-4000-8000-000000000000"))
    expired = user_client.post(runs, json=_apply(old))
    other_group = user_client.post(
        runs, json=_apply(preview) | {"groups": [{"group_id": "otro", "keep": "2024/a.pdf"}]}
    )
    bad_keep = user_client.post(runs, json=_apply(preview) | {"groups": [{"group_id": GROUP, "keep": "2024/otro.pdf"}]})

    assert ok.status_code == 202 and ok.json()["params"]["dry_run"] is True and ok.json()["is_write"] is False
    # La lista de grupos (hasta 10 000) no se repite en cada respuesta: solo su número.
    assert ok.json()["params"]["groups"] == 1
    repeated = user_client.post(
        runs,
        json=_apply(preview)
        | {"groups": [{"group_id": GROUP, "keep": "2024/a.pdf"}, {"group_id": GROUP, "keep": "2025/a copia.pdf"}]},
    )
    assert repeated.json()["code"] == "group_not_in_preview"
    assert no_preview.json()["code"] == "duplicates_preview_required"
    assert expired.json()["code"] == "duplicates_preview_required"
    assert other_group.json()["code"] == "group_not_in_preview"
    assert bad_keep.json()["code"] == "group_not_in_preview"


def test_move_is_for_owners_and_needs_a_writable_source(
    user_client: TestClient, project: dict[str, object], db: Session, make_user: Callable[..., User]
) -> None:
    editor = _member(user_client, project["id"], make_user, "editora", "editor")
    runs = f"/api/v1/projects/{project['id']}/runs"
    preview = _finished_preview(user_client, db, project["id"])

    assert editor.post(runs, json=_apply(preview, "copy")).status_code == 202
    assert editor.post(runs, json=_apply(preview, "move")).status_code == 403
    assert user_client.post(runs, json=_apply(preview, "move")).json()["code"] == "location_read_only"
    db.execute(update(Location).where(Location.name == "Origen").values(access="rw"))
    db.commit()
    assert user_client.post(runs, json=_apply(preview, "move")).status_code == 202


def test_real_apply_needs_its_own_preview_and_the_project_name(
    user_client: TestClient, project: dict[str, object], db: Session
) -> None:
    runs = f"/api/v1/projects/{project['id']}/runs"
    preview = _finished_preview(user_client, db, project["id"])
    dry = user_client.post(runs, json=_apply(preview)).json()
    db.execute(update(Run).where(Run.id == dry["id"]).values(status="succeeded", finished_at=utcnow()))
    db.commit()

    without = user_client.post(runs, json=_apply(preview, dry_run=False))
    wrong_name = user_client.post(
        runs, json=_apply(preview, dry_run=False, preview_run_id=dry["id"], confirm_name="Otro")
    )
    real = user_client.post(
        runs, json=_apply(preview, dry_run=False, preview_run_id=dry["id"], confirm_name="Proyecto A")
    )

    assert without.json()["code"] == "preview_required"
    assert wrong_name.json()["code"] == "preview_required"
    assert real.status_code == 202, real.json()
    assert real.json()["is_write"] is True


def test_groups_page_and_last_runs(user_client: TestClient, project: dict[str, object], db: Session) -> None:
    preview = _finished_preview(user_client, db, project["id"])

    page = user_client.get(f"/api/v1/runs/{preview}/duplicate-groups").json()
    versions = user_client.get(f"/api/v1/runs/{preview}/duplicate-groups", params={"reason": "version_conflict"}).json()
    last = user_client.get(f"/api/v1/projects/{project['id']}/duplicates/last").json()

    assert page["total"] == 1 and page["run"]["id"] == preview
    group = page["items"][0]
    assert group["reason"] == "exact_duplicate"
    assert [(m["key"], m["canonical"], m["output_path"]) for m in group["members"]] == [
        ("2024/a.pdf", True, "2024/a.md"),
        ("2025/a copia.pdf", False, "2025/a copia.md"),
    ]
    assert versions == {"run": page["run"], "items": [], "total": 0}
    assert last["preview"]["id"] == preview and last["apply"] is None
