"""web 2.7 (ADR-017): exclusiones del proyecto (rutas y patrones), preset de carpetas de sistema y exclusión efectiva
copiada en el escaneo y en la búsqueda de duplicados. Validación, permisos, auditoría y aviso «las exclusiones
cambiaron» en duplicados."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import AuditEntry, Location, Project, Run, Tenant, User, utcnow
from app.domain.projects.exclusions import SYSTEM_PATTERNS, EffectiveExclusion, PathFilter, check_project_patterns
from app.domain.scan.errors import InvalidExclusionError
from tests.conftest import USER_PASSWORD, login_as, project_payload


@pytest.fixture
def source(migrated: Settings, project_locations: dict[str, Location]) -> Path:
    root = migrated.locations_root / "origen"
    for sub in ("2024/borradores/viejos", "2024/fotos", "2025/otros"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture
def project(user_client: TestClient, project_locations: dict[str, Location], source: Path) -> dict[str, object]:
    response = user_client.post(
        "/api/v1/projects", json=project_payload(project_locations, source_subpaths=["2024", "2025"])
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


def _url(project: dict[str, object]) -> str:
    return f"/api/v1/projects/{project['id']}/exclusions"


def _put(
    client: TestClient,
    project: dict[str, object],
    excluded: list[str],
    patterns: list[str] | None = None,
    system: bool = True,
) -> Response:
    body = {"excluded": excluded, "ignore_patterns": patterns or [], "exclude_system_folders": system}
    return client.put(_url(project), json=body)


def test_a_new_project_excludes_system_folders(user_client: TestClient, project: dict[str, object]) -> None:
    body = user_client.get(_url(project)).json()

    assert body["excluded"] == [] and body["ignore_patterns"] == []
    assert body["exclude_system_folders"] is True
    assert body["system_patterns"] == list(SYSTEM_PATTERNS)
    assert body["location_patterns"] == []


def test_owner_sets_paths_and_patterns_collapsed_and_audited(
    user_client: TestClient, project: dict[str, object], db: Session
) -> None:
    response = _put(
        user_client,
        project,
        ["2024/borradores", "2024/borradores/viejos", "2025/otros", "2025/no-existe"],
        ["*.tmp", "old_*", "*.tmp"],
        system=False,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["excluded"] == [
        {"path": "2024/borradores", "exists": True},
        {"path": "2025/no-existe", "exists": False},
        {"path": "2025/otros", "exists": True},
    ]
    assert body["ignore_patterns"] == ["*.tmp", "old_*"] and body["exclude_system_folders"] is False
    entry = db.scalars(select(AuditEntry).where(AuditEntry.action == "project.exclusions")).one()
    assert entry.details is not None and entry.details["after"]["excluded"] == [
        "2024/borradores",
        "2025/no-existe",
        "2025/otros",
    ]
    # Sin cambios, sin evento nuevo.
    _put(user_client, project, ["2024/borradores", "2025/no-existe", "2025/otros"], ["*.tmp", "old_*"], system=False)
    assert len(db.scalars(select(AuditEntry).where(AuditEntry.action == "project.exclusions")).all()) == 1


@pytest.mark.parametrize(
    ("excluded", "patterns"),
    [
        (["2024"], []),  # la propia carpeta del proyecto
        (["otra"], []),  # fuera de las carpetas del proyecto
        (["../fuera"], []),  # traversal
        ([], ["*"]),  # lo excluiría todo
        ([], ["*.*"]),
        ([], ["a/b"]),  # con separador
    ],
)
def test_invalid_paths_and_patterns_are_rejected(
    user_client: TestClient, project: dict[str, object], excluded: list[str], patterns: list[str]
) -> None:
    response = _put(user_client, project, excluded, patterns)

    assert response.status_code in (400, 422), response.text


def test_only_the_owner_changes_them_members_read_and_other_tenants_get_404(
    user_client: TestClient,
    project: dict[str, object],
    make_user: Callable[..., User],
    make_tenant: Callable[..., Tenant],
) -> None:
    viewer = make_user("lectora")
    members = f"/api/v1/projects/{project['id']}/members"
    assert user_client.post(members, json={"user_id": viewer.id, "role": "viewer"}).status_code == 201
    other = make_tenant("obras", "Obras")
    make_user("bea", USER_PASSWORD, "admin", tenant_id=other.id)

    reader = login_as(user_client, "lectora")
    assert reader.get(_url(project)).status_code == 200
    assert _put(reader, project, ["2024/fotos"]).status_code == 403
    assert login_as(user_client, "bea").get(_url(project)).status_code == 404


def test_the_scan_copies_the_effective_exclusion(
    user_client: TestClient, project: dict[str, object], db: Session
) -> None:
    folder = user_client.put(
        f"/api/v1/projects/{project['id']}/scanned-folders/exclusions",
        params={"subpath": "2024"},
        json={"excluded": ["2024/fotos"]},
    )
    assert folder.status_code == 200, folder.text
    assert _put(user_client, project, ["2024/borradores", "2025/otros"], ["*.tmp"]).status_code == 200
    location = db.get(Location, project["source_location"]["id"])  # type: ignore[index]
    assert location is not None
    location.ignore_patterns = ["~$*", "*.bak"]
    db.commit()

    response = user_client.post(f"/api/v1/projects/{project['id']}/runs", json={"operation": "scan"})

    assert response.status_code == 202, response.text
    params = response.json()["params"]
    assert params["exclusions"] == {"2024": ["borradores", "fotos"], "2025": ["otros"]}
    # Ubicación, proyecto y preset, sin repetir (``~$*`` está en la ubicación y en el preset).
    assert params["ignore_patterns"] == ["~$*", "*.bak", "*.tmp", *[p for p in SYSTEM_PATTERNS if p != "~$*"]]


def test_the_dedup_preview_copies_the_exclusion_and_its_own_extra_paths(
    user_client: TestClient, project: dict[str, object], db: Session
) -> None:
    assert _put(user_client, project, ["2025/otros"], system=False).status_code == 200

    response = user_client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json={"operation": "dedup_preview", "extra_excluded_paths": ["2024/fotos"], "exclusion": {"paths": ["x"]}},
    )

    assert response.status_code == 202, response.text
    params = response.json()["params"]
    assert params["extra_excluded_paths"] == ["2024/fotos"]
    assert params["exclusion"]["paths"] == ["2024/fotos", "2025/otros"]
    assert params["exclusion"]["fingerprint"]
    bad = user_client.post(
        f"/api/v1/projects/{project['id']}/runs",
        json={"operation": "dedup_preview", "extra_excluded_paths": ["../fuera"]},
    )
    assert bad.status_code in (400, 422)


def test_duplicates_warn_and_apply_refuses_when_exclusions_changed(
    user_client: TestClient, project: dict[str, object], db: Session
) -> None:
    runs = f"/api/v1/projects/{project['id']}/runs"
    preview = user_client.post(runs, json={"operation": "dedup_preview"}).json()
    run = db.get(Run, preview["id"])
    assert run is not None
    run.status, run.started_at, run.finished_at = "succeeded", utcnow(), utcnow()
    db.commit()
    last = f"/api/v1/projects/{project['id']}/duplicates/last"
    assert user_client.get(last).json()["exclusions_changed"] is False

    # Cambian las de una carpeta guardada (no tocan ``projects.updated_at``).
    changed = user_client.put(
        f"/api/v1/projects/{project['id']}/scanned-folders/exclusions",
        params={"subpath": "2024"},
        json={"excluded": ["2024/fotos"]},
    )
    assert changed.status_code == 200

    assert user_client.get(last).json()["exclusions_changed"] is True
    applied = user_client.post(
        runs,
        json={
            "operation": "dedup_apply",
            "groups_run_id": run.id,
            "groups": [{"group_id": "g", "keep": "2024/a.txt"}],
        },
    )
    assert applied.status_code == 409 and applied.json()["code"] == "exclusions_changed"


def test_the_new_project_is_saved_with_the_preset(db: Session, project: dict[str, object]) -> None:
    """El alta lo activa; los proyectos de antes de la 0033 quedan sin él (``server_default``, test de migraciones)."""
    loaded = db.get(Project, project["id"])
    assert loaded is not None and loaded.exclude_system_folders is True


# --- lógica pura ----------------------------------------------------------------------------------------------------


def test_effective_exclusion_per_folder_and_fingerprint() -> None:
    exclusion = EffectiveExclusion(paths=["2024/a", "2024/b/c", "2025/x"], patterns=["*.tmp"])

    assert exclusion.for_folder("2024") == ["a", "b/c"]
    assert exclusion.for_folder("") == ["2024/a", "2024/b/c", "2025/x"]
    assert (
        exclusion.fingerprint()
        == EffectiveExclusion(paths=["2025/x", "2024/b/c", "2024/a"], patterns=["*.tmp"]).fingerprint()
    )
    assert exclusion.fingerprint() != EffectiveExclusion(paths=["2024/a"], patterns=["*.tmp"]).fingerprint()


def test_path_filter_covers_paths_and_patterns_under_the_root(tmp_path: Path) -> None:
    root = tmp_path / "origen" / "2024"
    matcher = PathFilter([root], [root / "fotos"], ["#recycle", "~$*"])

    assert matcher.covers(str(root / "fotos" / "a.jpg"))
    assert matcher.covers(str(root / "fotos"))
    assert not matcher.covers(str(root / "fotos-2" / "a.jpg"))
    assert matcher.covers(str(root / "#recycle" / "x.pdf"))
    assert matcher.covers(str(root / "actas" / "~$acta.docx"))
    assert not matcher.covers(str(root / "actas" / "acta.docx"))
    # Los patrones solo miran los tramos por debajo de la carpeta escaneada.
    assert not PathFilter([root], [], ["origen"]).covers(str(root / "a.pdf"))
    assert PathFilter([], [], []).empty


def test_project_patterns_reject_match_all() -> None:
    assert check_project_patterns(["*.tmp", " old_* "]) == ["*.tmp", "old_*"]
    for pattern in ("*", "**", "*.*", "?*", "***"):
        with pytest.raises(InvalidExclusionError):
            check_project_patterns([pattern])
