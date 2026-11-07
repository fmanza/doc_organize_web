"""web 1.4.0 (doc_organize 1.3.0, G41): subcarpetas excluidas por carpeta guardada y patrones de nombre por ubicación
de origen. Validación, permisos (403 sin ``owner``, 404 desde otro tenant), auditoría y copia en el run al encolar."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import AuditEntry, Location, Run, Tenant, User, utcnow
from tests.conftest import USER_PASSWORD, login_as, project_payload


@pytest.fixture
def source(migrated: Settings, project_locations: dict[str, Location]) -> Path:
    root = migrated.locations_root / "origen"
    for sub in ("2024/borradores/viejos", "2024/fotos", "2024/Actas", "2025/otros"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture
def project(user_client: TestClient, project_locations: dict[str, Location], source: Path) -> dict[str, object]:
    response = user_client.post("/api/v1/projects", json=project_payload(project_locations))
    assert response.status_code == 201, response.text
    return dict(response.json())


def _url(project: dict[str, object]) -> str:
    return f"/api/v1/projects/{project['id']}/scanned-folders/exclusions"


def _put(client: TestClient, project: dict[str, object], excluded: list[str], subpath: str = "2024") -> Response:
    return client.put(_url(project), params={"subpath": subpath}, json={"excluded": excluded})


# --- exclusiones por carpeta guardada -------------------------------------------------------------------------------


def test_owner_excludes_subfolders_and_they_are_listed(
    user_client: TestClient, project: dict[str, object], db: Session
) -> None:
    response = user_client.put(
        _url(project),
        params={"subpath": "2024"},
        json={"excluded": ["2024/fotos", "2024/borradores", "2024/borradores/viejos", "2024/fotos"]},
    )

    assert response.status_code == 200, response.text
    # Las redundantes (una dentro de otra) y las repetidas se colapsan; las rutas son relativas a la ubicación.
    assert response.json()["excluded"] == [
        {"subpath": "2024/borradores", "exists": True},
        {"subpath": "2024/fotos", "exists": True},
    ]
    listed = user_client.get(f"/api/v1/projects/{project['id']}/scanned-folders").json()["items"]
    assert listed[0]["excluded"] == response.json()["excluded"]
    entry = db.scalars(select(AuditEntry).where(AuditEntry.action == "project.scan_folder_exclusions")).one()
    assert entry.details == {"subpath": "2024", "before": [], "after": ["borradores", "fotos"]}


def test_a_missing_exclusion_is_kept_and_can_be_removed(
    user_client: TestClient, project: dict[str, object], source: Path, db: Session
) -> None:
    assert _put(user_client, project, ["2024/fotos", "2024/ya-no-existe"]).status_code == 200
    (source / "2024" / "fotos").rmdir()

    listed = user_client.get(f"/api/v1/projects/{project['id']}/scanned-folders").json()["items"][0]
    assert listed["excluded"] == [
        {"subpath": "2024/fotos", "exists": False},
        {"subpath": "2024/ya-no-existe", "exists": False},
    ]
    response = _put(user_client, project, ["2024/ya-no-existe"])
    assert response.json()["excluded"] == [{"subpath": "2024/ya-no-existe", "exists": False}]
    cleared = _put(user_client, project, [])
    assert cleared.json()["excluded"] == []
    assert len(db.scalars(select(AuditEntry).where(AuditEntry.action == "project.scan_folder_exclusions")).all()) == 3


@pytest.mark.parametrize(
    "excluded",
    [
        ["2024"],  # la propia carpeta
        [""],  # la raíz de la ubicación
        ["2025/otros"],  # fuera de la carpeta
        ["2024/../2025"],  # sintaxis no válida
        ["/2024/fotos"],
        [f"2024/sub{i}" for i in range(51)],  # más de 50
    ],
)
def test_invalid_exclusions_are_rejected(
    user_client: TestClient, project: dict[str, object], excluded: list[str]
) -> None:
    response = _put(user_client, project, excluded)

    assert response.status_code == 400, response.text


def test_an_exclusion_that_is_a_file_cannot_be_resolved(
    user_client: TestClient, project: dict[str, object], source: Path
) -> None:
    response = _put(user_client, project, ["2024/factura.txt"])

    assert response.status_code == 400 and response.json()["code"] == "invalid_exclusion"


@pytest.mark.skipif(os.name == "nt", reason="los enlaces simbólicos exigen privilegios en Windows")
def test_a_link_is_not_excluded_in_place_of_its_target(
    user_client: TestClient, project: dict[str, object], source: Path
) -> None:
    """El escaneo no sigue enlaces: excluir el destino de uno excluiría otra carpeta."""
    (source / "2024" / "atajo").symlink_to(source / "2024" / "fotos", target_is_directory=True)

    response = _put(user_client, project, ["2024/atajo"])

    assert response.status_code == 400 and response.json()["code"] == "invalid_exclusion"


def test_unknown_saved_folder_is_404(user_client: TestClient, project: dict[str, object]) -> None:
    assert _put(user_client, project, [], subpath="2025").status_code == 404


def test_only_the_owner_excludes_and_other_tenants_get_404(
    user_client: TestClient,
    project: dict[str, object],
    make_user: Callable[..., User],
    make_tenant: Callable[..., Tenant],
) -> None:
    editor = make_user("editora")
    assert (
        user_client.post(
            f"/api/v1/projects/{project['id']}/members", json={"user_id": editor.id, "role": "editor"}
        ).status_code
        == 201
    )
    other = make_tenant("obras", "Obras")
    make_user("bea", USER_PASSWORD, "admin", tenant_id=other.id)

    assert _put(login_as(user_client, "editora"), project, ["2024/fotos"]).status_code == 403
    assert _put(login_as(user_client, "bea"), project, ["2024/fotos"]).status_code == 404


def test_exclusions_change_while_a_scan_runs(user_client: TestClient, project: dict[str, object]) -> None:
    """A diferencia de añadir o quitar carpetas: el run en marcha sigue con la copia que hizo al encolarse."""
    assert user_client.post(f"/api/v1/projects/{project['id']}/runs", json={"operation": "scan"}).status_code == 202

    assert _put(user_client, project, ["2024/fotos"]).status_code == 200


# --- copia en el run ------------------------------------------------------------------------------------------------


def test_the_run_copies_exclusions_and_patterns_when_enqueued(
    user_client: TestClient, project: dict[str, object], db: Session
) -> None:
    source_id = project["source_location"]["id"]  # type: ignore[index]
    assert _put(user_client, project, ["2024/fotos"]).status_code == 200
    location = db.get(Location, source_id)
    assert location is not None
    location.ignore_patterns = ["~$*"]
    db.commit()

    response = user_client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json={"operation": "scan", "exclusions": {"2024": ["otra"]}, "ignore_patterns": ["*.pdf"]},
    )

    assert response.status_code == 202, response.text
    params = response.json()["params"]
    # Lo que mande el cliente se descarta: manda lo guardado.
    assert params["exclusions"] == {"2024": ["fotos"]} and params["ignore_patterns"] == ["~$*"]


def test_changing_exclusions_invalidates_a_force_preview(
    user_client: TestClient, project: dict[str, object], db: Session
) -> None:
    url = f"/api/v1/projects/{project['id']}/runs"
    preview = user_client.post(url, json={"operation": "scan", "force": True, "dry_run": True}).json()
    run = db.get(Run, preview["id"])
    assert run is not None
    run.status, run.started_at, run.finished_at = "succeeded", utcnow(), utcnow()
    db.commit()
    assert _put(user_client, project, ["2024/fotos"]).status_code == 200

    real = user_client.post(
        url, json={"operation": "scan", "force": True, "preview_run_id": run.id, "confirm_name": "Proyecto A"}
    )

    assert real.json()["code"] == "preview_required"


# --- patrones por ubicación -----------------------------------------------------------------------------------------


def test_admin_sets_ignore_patterns_on_a_source_location(
    admin_client: TestClient, project_locations: dict[str, Location], db: Session
) -> None:
    url = f"/api/v1/locations/{project_locations['source'].id}"
    patterns = ["~$*", "@eaDir", "#recycle", "$RECYCLE.BIN", "System Volume Information", "~$*"]

    response = admin_client.patch(url, json={"ignore_patterns": patterns})

    assert response.status_code == 200, response.text
    assert response.json()["ignore_patterns"] == patterns[:-1]  # sin repetidos, en su orden
    assert admin_client.get(url).json()["ignore_patterns"] == patterns[:-1]
    entry = db.scalars(
        select(AuditEntry).where(AuditEntry.action == "location.update").order_by(AuditEntry.id.desc())
    ).first()
    assert entry is not None and entry.details is not None
    assert entry.details["fields"] == ["ignore_patterns"]
    assert entry.details["ignore_patterns"] == {"before": [], "after": patterns[:-1]}
    assert admin_client.get(f"/api/v1/locations/{project_locations['destination'].id}").json()["ignore_patterns"] == []


@pytest.mark.parametrize(
    "patterns",
    [
        [f"p{i}" for i in range(31)],
        [""],
        ["   "],
        ["fotos/*.jpg"],
        ["fotos\\*.jpg"],
        ["x" * 65],
    ],
)
def test_invalid_ignore_patterns_are_rejected(
    admin_client: TestClient, project_locations: dict[str, Location], patterns: list[str]
) -> None:
    response = admin_client.patch(
        f"/api/v1/locations/{project_locations['source'].id}", json={"ignore_patterns": patterns}
    )

    assert response.status_code == 400, response.text
    assert response.json()["code"] == "invalid_ignore_patterns"


def test_ignore_patterns_are_only_for_source_locations(
    admin_client: TestClient, project_locations: dict[str, Location]
) -> None:
    url = f"/api/v1/locations/{project_locations['destination'].id}"

    assert admin_client.patch(url, json={"ignore_patterns": ["~$*"]}).status_code == 400
    assert admin_client.patch(url, json={"ignore_patterns": []}).status_code == 200


def test_only_admins_change_ignore_patterns(user_client: TestClient, project_locations: dict[str, Location]) -> None:
    response = user_client.patch(
        f"/api/v1/locations/{project_locations['source'].id}", json={"ignore_patterns": ["~$*"]}
    )

    assert response.status_code == 403
