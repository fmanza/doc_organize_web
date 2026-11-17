"""Versiones del manifiesto de taxonomía (1.8.0): guardar con ``If-Match``, versión de lo que había, recorte a 5,
borrar, ver y restaurar (también una versión «sin manifiesto» o no válida), permisos, IDOR, bloqueo de escritura,
orden versión-escritura y plantillas incluidas aceptadas como manifiesto. «Vaciar histórico» está en
``tests/jobs/test_worker.py``."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import AuditEntry, Location, ProjectManifestVersion, Run, User
from app.domain.context import manifest_versions
from app.domain.locations.errors import LocationUnavailableError
from app.integrations.doc_organize import DocOrganizeOperationError
from app.integrations.doc_organize import context as library
from tests.api.test_context import TEMPLATE
from tests.conftest import login_as, project_payload

OTHER = TEMPLATE.replace("title: Obras", "title: Otra")


@pytest.fixture
def project(user_client: TestClient, project_locations: dict[str, Location]) -> dict[str, object]:
    response = user_client.post("/api/v1/projects", json=project_payload(project_locations))
    assert response.status_code == 201, response.text
    return dict(response.json())


@pytest.fixture
def url(project: dict[str, object]) -> str:
    return f"/api/v1/projects/{project['id']}/context/taxonomy-manifest"


@pytest.fixture
def target(migrated: Settings) -> Path:
    return migrated.locations_root / "salidas" / "Proyecto A" / "taxonomy_manifest.md"


def _etag(client: TestClient, url: str) -> str:
    return str(client.get(url).json()["etag"])


def _save(client: TestClient, url: str, markdown: str) -> dict[str, object]:
    response = client.put(url, json={"markdown": markdown}, headers={"If-Match": _etag(client, url)})
    assert response.status_code == 200, response.text
    return dict(response.json())


def _versions(client: TestClient, url: str) -> list[dict[str, object]]:
    response = client.get(f"{url}/versions")
    assert response.status_code == 200, response.text
    return list(response.json()["items"])


def _member(client: TestClient, project_id: object, make_user: Callable[..., User], name: str, role: str) -> TestClient:
    other = make_user(name)
    added = client.post(f"/api/v1/projects/{project_id}/members", json={"user_id": other.id, "role": role})
    assert added.status_code == 201
    return login_as(client, name)


def test_saving_needs_the_etag_and_keeps_what_was_there(user_client: TestClient, url: str, target: Path) -> None:
    assert user_client.put(url, json={"markdown": TEMPLATE}).json()["code"] == "etag_required"

    first = _save(user_client, url, TEMPLATE)
    assert first["etag"] == manifest_versions.manifest_etag(TEMPLATE)
    assert first["last_changed_at"] is not None
    [created] = _versions(user_client, url)
    assert created["action"] == "save" and created["empty"] and not created["valid"]

    _save(user_client, url, OTHER)
    newest = _versions(user_client, url)[0]
    assert (newest["valid"], newest["domains"], newest["material_types"]) == (True, 2, 1)
    detail = user_client.get(f"{url}/versions/{newest['id']}").json()
    assert detail["markdown"] == TEMPLATE
    assert target.read_text(encoding="utf-8") == OTHER


def test_saving_the_same_text_creates_no_version(user_client: TestClient, url: str) -> None:
    _save(user_client, url, TEMPLATE)
    _save(user_client, url, TEMPLATE)
    assert len(_versions(user_client, url)) == 1


def test_a_stale_etag_is_rejected_without_writing(user_client: TestClient, url: str, target: Path) -> None:
    stale = _etag(user_client, url)
    _save(user_client, url, TEMPLATE)

    response = user_client.put(url, json={"markdown": OTHER}, headers={"If-Match": stale})

    assert (response.status_code, response.json()["code"]) == (409, "manifest_changed")
    assert target.read_text(encoding="utf-8") == TEMPLATE
    assert len(_versions(user_client, url)) == 1


def test_a_manifest_edited_outside_is_caught_by_the_etag_and_kept_as_version(
    user_client: TestClient, url: str, target: Path
) -> None:
    _save(user_client, url, TEMPLATE)
    old = _etag(user_client, url)
    target.write_text(OTHER, encoding="utf-8")  # editado en la carpeta compartida

    assert user_client.put(url, json={"markdown": TEMPLATE}, headers={"If-Match": old}).status_code == 409
    _save(user_client, url, TEMPLATE)
    newest = _versions(user_client, url)[0]
    assert user_client.get(f"{url}/versions/{newest['id']}").json()["markdown"] == OTHER


def test_only_the_last_five_versions_are_kept(user_client: TestClient, url: str, db: Session) -> None:
    for number in range(7):
        _save(user_client, url, TEMPLATE.replace("Obras", f"Obras {number}"))

    versions = _versions(user_client, url)
    assert len(versions) == manifest_versions.MAX_MANIFEST_VERSIONS == 5
    assert db.scalar(select(ProjectManifestVersion.id).where(ProjectManifestVersion.markdown.is_(None))) is None
    newest = user_client.get(f"{url}/versions/{versions[0]['id']}").json()["markdown"]
    assert "Obras 5" in newest


def test_delete_keeps_a_version_and_restore_brings_it_back(user_client: TestClient, url: str, target: Path) -> None:
    _save(user_client, url, TEMPLATE)

    deleted = user_client.delete(url, headers={"If-Match": _etag(user_client, url)})
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["markdown"] is None and deleted.json()["etag"] == "none"
    assert not target.exists()
    assert user_client.delete(url, headers={"If-Match": "none"}).json()["code"] == "manifest_not_found"

    newest = _versions(user_client, url)[0]
    assert newest["action"] == "delete" and newest["valid"]
    restored = user_client.post(f"{url}/versions/{newest['id']}/restore", headers={"If-Match": "none"})
    assert restored.status_code == 200, restored.text
    assert target.read_text(encoding="utf-8") == TEMPLATE
    assert _versions(user_client, url)[0]["action"] == "restore"  # restaurar también se puede deshacer


def test_restoring_an_empty_version_deletes_the_file(user_client: TestClient, url: str, target: Path) -> None:
    _save(user_client, url, TEMPLATE)
    [empty] = _versions(user_client, url)

    response = user_client.post(f"{url}/versions/{empty['id']}/restore", headers={"If-Match": _etag(user_client, url)})

    assert response.status_code == 200, response.text
    assert not target.exists()
    assert _versions(user_client, url)[0]["action"] == "restore"


def test_an_invalid_version_is_not_restored(
    user_client: TestClient, url: str, target: Path, project: dict[str, object], db: Session
) -> None:
    db.add(ProjectManifestVersion(project_id=int(str(project["id"])), action="save", markdown="---\nroto: [\n---\n"))
    db.commit()
    broken = _versions(user_client, url)[0]
    assert not broken["valid"] and not broken["empty"]

    response = user_client.post(f"{url}/versions/{broken['id']}/restore", headers={"If-Match": "none"})

    assert (response.status_code, response.json()["code"]) == (422, "manifest_version_invalid")
    assert not target.exists()


def test_versions_follow_project_permissions(
    user_client: TestClient, url: str, project: dict[str, object], make_user: Callable[..., User]
) -> None:
    _save(user_client, url, TEMPLATE)
    [version] = _versions(user_client, url)
    viewer = _member(user_client, project["id"], make_user, "lectora", "viewer")

    assert len(_versions(viewer, url)) == 1
    assert viewer.get(f"{url}/versions/{version['id']}").status_code == 200
    etag = _etag(viewer, url)
    assert viewer.post(f"{url}/versions/{version['id']}/restore", headers={"If-Match": etag}).status_code == 403
    assert viewer.delete(url, headers={"If-Match": etag}).status_code == 403

    make_user("ajena")
    outsider = login_as(user_client, "ajena")
    assert outsider.get(f"{url}/versions").status_code == 404
    assert outsider.get(f"{url}/versions/{version['id']}").status_code == 404


def test_a_version_of_another_project_is_not_found(
    user_client: TestClient, url: str, project_locations: dict[str, Location]
) -> None:
    other = user_client.post("/api/v1/projects", json=project_payload(project_locations, name="Proyecto B")).json()
    other_url = f"/api/v1/projects/{other['id']}/context/taxonomy-manifest"
    _save(user_client, other_url, TEMPLATE)
    [foreign] = _versions(user_client, other_url)

    assert user_client.get(f"{url}/versions/{foreign['id']}").json()["code"] == "manifest_version_not_found"
    restore = user_client.post(f"{url}/versions/{foreign['id']}/restore", headers={"If-Match": "none"})
    assert restore.json()["code"] == "manifest_version_not_found"


def test_changes_wait_for_writes_and_need_a_writable_destination(
    user_client: TestClient, url: str, project: dict[str, object], db: Session
) -> None:
    _save(user_client, url, TEMPLATE)
    [version] = _versions(user_client, url)
    etag = {"If-Match": _etag(user_client, url)}
    run = user_client.post(f"/api/v1/projects/{project['id']}/runs", json={"operation": "search_index"}).json()

    assert user_client.delete(url, headers=etag).json()["code"] == "write_locked"
    assert user_client.post(f"{url}/versions/{version['id']}/restore", headers=etag).json()["code"] == "write_locked"
    db.execute(update(Run).where(Run.id == run["id"]).values(status="succeeded"))
    db.execute(update(Location).where(Location.name == "Salidas").values(access="ro"))
    db.commit()
    assert user_client.delete(url, headers=etag).json()["code"] == "location_read_only"


def test_audit_never_stores_the_markdown(user_client: TestClient, url: str, db: Session) -> None:
    _save(user_client, url, TEMPLATE)
    user_client.delete(url, headers={"If-Match": _etag(user_client, url)})
    [deleted, _] = _versions(user_client, url)
    user_client.post(f"{url}/versions/{deleted['id']}/restore", headers={"If-Match": "none"})

    entries = list(db.scalars(select(AuditEntry).where(AuditEntry.action.like("project.taxonomy_manifest_%"))))
    assert {entry.action for entry in entries} == {
        "project.taxonomy_manifest_save",
        "project.taxonomy_manifest_delete",
        "project.taxonomy_manifest_restore",
    }
    assert all("Plantilla sintética" not in str(entry.details) for entry in entries)


def test_a_failed_write_leaves_no_version(
    user_client: TestClient, url: str, target: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _fail(*args: object, **kwargs: object) -> None:
        raise DocOrganizeOperationError("disco lleno")

    monkeypatch.setattr(library, "save_manifest", _fail)
    response = user_client.put(url, json={"markdown": TEMPLATE}, headers={"If-Match": "none"})

    assert response.status_code == 503
    assert _versions(user_client, url) == []
    assert not target.exists()


def test_a_timed_out_write_keeps_the_version(
    user_client: TestClient, url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _slow(*args: object, **kwargs: object) -> None:
        raise LocationUnavailableError("La ubicación no responde a tiempo.")

    monkeypatch.setattr(library, "save_manifest", _slow)
    response = user_client.put(url, json={"markdown": TEMPLATE}, headers={"If-Match": "none"})

    assert response.status_code == 503
    assert len(_versions(user_client, url)) == 1  # lo que había (nada): restaurarla es inocuo


@pytest.mark.skipif(sys.platform == "win32", reason="enlaces simbólicos")
def test_delete_does_not_follow_a_link(user_client: TestClient, url: str, target: Path, tmp_path: Path) -> None:
    outside = tmp_path / "fuera.md"
    outside.write_text(TEMPLATE, encoding="utf-8")
    target.symlink_to(outside)

    response = user_client.delete(url, headers={"If-Match": "none"})

    assert response.json()["code"] == "manifest_replaced"
    assert outside.read_text(encoding="utf-8") == TEMPLATE
    assert target.is_symlink()


def test_every_builtin_template_is_accepted_as_manifest(user_client: TestClient, url: str) -> None:
    """F4: «Personalizar para este proyecto» copia el Markdown de la plantilla al manifiesto."""
    names = list(library.builtin_templates())
    assert names
    for name in names:
        markdown = user_client.get(f"/api/v1/taxonomy-templates/{name}").json()["markdown"]
        response = user_client.put(url, json={"markdown": markdown}, headers={"If-Match": _etag(user_client, url)})
        assert response.status_code == 200, f"{name}: {response.text}"
