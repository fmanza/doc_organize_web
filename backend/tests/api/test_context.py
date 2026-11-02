"""Contexto y taxonomías (Fase 7) en la API: plantillas (incluidas de solo lectura, CRUD de admin, validación,
descarga), contexto y documentos de la proyección, manifiesto del proyecto, encolar ``context_build`` y
``context_delete`` (roles, carpeta, plantilla vigente, vista previa) y el sitio aislado (token, cabeceras, rutas).
El trabajo del worker está en ``tests/jobs/test_context_operation.py``."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import AuditEntry, ContextDocument, Location, ProjectContext, Run, User, UserSession, utcnow
from app.domain.context import site
from tests.conftest import ADMIN_PASSWORD, login_as, project_payload

TEMPLATE = """---
title: Obras
description: Catálogo de prueba
domains:
  - slug: facturas
    name: Facturas
    keywords: [factura]
  - slug: informes
    name: Informes
material_types:
  - slug: original
    name: Original
---
# Notas

Plantilla sintética.
"""


@pytest.fixture
def project(user_client: TestClient, project_locations: dict[str, Location]) -> dict[str, object]:
    response = user_client.post(
        "/api/v1/projects", json=project_payload(project_locations, source_subpaths=["2024", "2025"])
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


def _member(client: TestClient, project_id: object, make_user: Callable[..., User], name: str, role: str) -> TestClient:
    other = make_user(name)
    assert (
        client.post(f"/api/v1/projects/{project_id}/members", json={"user_id": other.id, "role": role}).status_code
        == 201
    )
    return login_as(client, name)


def _seed_context(db: Session, project_id: int, *, site_built: bool = True) -> None:
    """Proyección como la deja ``context_build``: un dominio con dos documentos y uno sin clasificar."""
    db.add(
        ProjectContext(
            project_id=project_id,
            output_folder_name="organizado",
            catalog_kind="discover",
            documents_count=2,
            unclassified_count=1,
            failed_count=1,
            collisions_count=0,
            site_built=site_built,
            domains=[
                {"slug": "facturas", "name": "Facturas", "description": None, "status": "borrador", "documents": 2}
            ],
        )
    )
    db.flush()
    db.add_all(
        [
            ContextDocument(
                project_id=project_id,
                seq=0,
                domain_slug="facturas",
                title="Factura enero",
                document_type="pdf",
                folder="2024",
                path="enero/factura.pdf",
                organized_path="organizado/facturas/pdf/factura/factura.pdf",
            ),
            ContextDocument(
                project_id=project_id,
                seq=1,
                domain_slug="facturas",
                title="Factura febrero",
                document_type="pdf",
                folder="2025",
                path="factura.pdf",
                failed=True,
            ),
            ContextDocument(project_id=project_id, seq=2, title="notas.txt", folder="2024", path="notas.txt"),
        ]
    )
    db.commit()


# --- plantillas ------------------------------------------------------------------------------------------------------


def test_builtin_templates_are_listed_and_read_only(admin_client: TestClient) -> None:
    items = admin_client.get("/api/v1/taxonomy-templates").json()["items"]
    builtin = {i["name"] for i in items if i["builtin"]}
    assert {"calidad", "sgi-integrado", "sgi-iso27001"} <= builtin

    detail = admin_client.get("/api/v1/taxonomy-templates/calidad").json()
    assert detail["markdown"].startswith("---\n") and detail["domains"] and detail["material_types"]
    assert admin_client.put("/api/v1/taxonomy-templates/calidad", json={"markdown": TEMPLATE}).json()["code"] == (
        "template_builtin"
    )
    assert admin_client.delete("/api/v1/taxonomy-templates/calidad").json()["code"] == "template_builtin"


def test_admin_creates_updates_and_deletes_custom_templates(admin_client: TestClient, db: Session) -> None:
    url = "/api/v1/taxonomy-templates/obras-2026"

    created = admin_client.put(url, json={"markdown": TEMPLATE})
    updated = admin_client.put(url, json={"markdown": TEMPLATE.replace("title: Obras", "title: Obras v2")})

    assert created.status_code == 201, created.text
    assert created.json()["domains"] == [
        {"slug": "facturas", "name": "Facturas"},
        {"slug": "informes", "name": "Informes"},
    ]
    assert updated.status_code == 200 and updated.json()["title"] == "Obras v2"
    listed = {i["name"]: i for i in admin_client.get("/api/v1/taxonomy-templates").json()["items"]}
    assert listed["obras-2026"]["builtin"] is False and listed["obras-2026"]["description"] == "Catálogo de prueba"

    download = admin_client.get(f"{url}/download")
    assert download.headers["content-type"].startswith("text/markdown")
    assert (
        "attachment" in download.headers["content-disposition"]
        and "obras-2026.md" in download.headers["content-disposition"]
    )
    assert download.text.startswith("---\ntitle: Obras v2")

    assert admin_client.delete(url).status_code == 204
    assert admin_client.get(url).json()["code"] == "template_not_found"
    actions = set(db.scalars(select(AuditEntry.action).where(AuditEntry.target_type == "taxonomy_template")))
    assert actions == {"taxonomy_template.save", "taxonomy_template.delete"}


@pytest.mark.parametrize(
    ("name", "markdown"),
    [
        ("Mayúsculas", TEMPLATE),
        ("buena", "sin front matter"),
        ("buena", "---\ndomains: [1, 2]\n---\n"),
        ("buena", "---\ndomains:\n  - slug: a\n---\n"),
    ],
)
def test_invalid_templates_are_rejected(admin_client: TestClient, name: str, markdown: str) -> None:
    response = admin_client.put(f"/api/v1/taxonomy-templates/{name}", json={"markdown": markdown})
    assert response.status_code == 422
    assert response.json()["code"] == "template_invalid"


def test_only_admins_change_templates(user_client: TestClient, admin: User) -> None:
    url = "/api/v1/taxonomy-templates/obras"
    admin_client = login_as(user_client, admin.username, ADMIN_PASSWORD)

    assert user_client.put(url, json={"markdown": TEMPLATE}).status_code == 403
    assert admin_client.put(url, json={"markdown": TEMPLATE}).status_code == 201
    assert user_client.get(url).status_code == 200
    assert user_client.delete(url).status_code == 403


def test_templates_need_a_session(client: TestClient, migrated: Settings) -> None:
    assert client.get("/api/v1/taxonomy-templates").status_code == 401


# --- contexto y documentos -------------------------------------------------------------------------------------------


def test_context_and_its_documents(user_client: TestClient, project: dict[str, object], db: Session) -> None:
    base = f"/api/v1/projects/{project['id']}/context"
    assert user_client.get(base).json()["code"] == "context_not_found"
    _seed_context(db, int(str(project["id"])))

    summary = user_client.get(base).json()
    domain = user_client.get(f"{base}/documents", params={"domain": "facturas", "limit": 1}).json()
    failed = user_client.get(f"{base}/documents", params={"domain": "facturas", "only": "failed"}).json()
    unclassified = user_client.get(f"{base}/documents").json()

    assert summary["documents_count"] == 2 and summary["domains"][0]["slug"] == "facturas"
    assert domain["total"] == 2 and domain["items"][0]["path"] == "enero/factura.pdf"
    assert domain["items"][0]["output_path"] == "2024/enero/factura.md"
    assert [i["title"] for i in failed["items"]] == ["Factura febrero"]
    assert [i["path"] for i in unclassified["items"]] == ["notas.txt"]
    assert user_client.get(f"{base}/documents", params={"domain": "otro"}).json()["code"] == "context_not_found"


def test_context_is_only_for_members(
    user_client: TestClient, project: dict[str, object], db: Session, make_user: Callable[..., User]
) -> None:
    _seed_context(db, int(str(project["id"])))
    make_user("ajena")
    outsider = login_as(user_client, "ajena")
    base = f"/api/v1/projects/{project['id']}/context"

    assert outsider.get(base).status_code == 404
    assert outsider.get(f"{base}/documents").status_code == 404
    assert outsider.post(f"{base}/site-session").status_code == 404
    assert outsider.get(f"{base}/taxonomy-manifest").status_code == 404


# --- manifiesto ------------------------------------------------------------------------------------------------------


def test_manifest_is_validated_and_written_by_editors(
    user_client: TestClient,
    project: dict[str, object],
    migrated: Settings,
    db: Session,
    make_user: Callable[..., User],
) -> None:
    url = f"/api/v1/projects/{project['id']}/context/taxonomy-manifest"
    viewer = _member(user_client, project["id"], make_user, "lectora", "viewer")
    target = migrated.locations_root / "salidas" / "Proyecto A" / "taxonomy_manifest.md"

    assert user_client.get(url).json() == {"markdown": None, "error": None, "domains": [], "material_types": []}
    assert viewer.put(url, json={"markdown": TEMPLATE}).status_code == 403
    assert user_client.put(url, json={"markdown": "no"}).json()["code"] == "template_invalid"
    saved = user_client.put(url, json={"markdown": TEMPLATE})

    assert saved.status_code == 200, saved.text
    assert target.read_text(encoding="utf-8") == TEMPLATE
    assert viewer.get(url).json()["domains"][0]["slug"] == "facturas"
    target.write_text("---\nroto: [\n---\n", encoding="utf-8")
    broken = user_client.get(url).json()
    assert broken["markdown"].startswith("---") and broken["error"]
    assert db.scalar(select(AuditEntry.action).where(AuditEntry.action == "project.taxonomy_manifest_save"))


def test_manifest_waits_for_writes_and_needs_a_writable_destination(
    user_client: TestClient, project: dict[str, object], db: Session
) -> None:
    url = f"/api/v1/projects/{project['id']}/context/taxonomy-manifest"
    run = user_client.post(f"/api/v1/projects/{project['id']}/runs", json={"operation": "search_index"}).json()
    assert user_client.put(url, json={"markdown": TEMPLATE}).json()["code"] == "write_locked"
    db.execute(update(Run).where(Run.id == run["id"]).values(status="succeeded"))
    db.execute(update(Location).where(Location.name == "Salidas").values(access="ro"))
    db.commit()
    assert user_client.put(url, json={"markdown": TEMPLATE}).json()["code"] == "location_read_only"


@pytest.mark.skipif(sys.platform == "win32", reason="enlaces simbólicos")
def test_a_linked_manifest_is_neither_read_nor_overwritten(
    user_client: TestClient, project: dict[str, object], migrated: Settings, tmp_path: Path
) -> None:
    outside = tmp_path / "fuera.md"
    outside.write_text(TEMPLATE, encoding="utf-8")
    (migrated.locations_root / "salidas" / "Proyecto A" / "taxonomy_manifest.md").symlink_to(outside)
    url = f"/api/v1/projects/{project['id']}/context/taxonomy-manifest"

    assert user_client.get(url).json()["code"] == "manifest_replaced"
    assert user_client.put(url, json={"markdown": TEMPLATE.replace("Obras", "Otra")}).json()["code"] == (
        "manifest_replaced"
    )
    assert outside.read_text(encoding="utf-8") == TEMPLATE


# --- encolar construir y borrar --------------------------------------------------------------------------------------


def test_build_is_for_editors_and_resolves_the_template(
    user_client: TestClient,
    admin: User,
    project: dict[str, object],
    db: Session,
    make_user: Callable[..., User],
) -> None:
    runs = f"/api/v1/projects/{project['id']}/runs"
    viewer = _member(user_client, project["id"], make_user, "lectora", "viewer")
    admin_client = login_as(user_client, admin.username, ADMIN_PASSWORD)
    assert admin_client.put("/api/v1/taxonomy-templates/obras", json={"markdown": TEMPLATE}).status_code == 201

    assert viewer.post(runs, json={"operation": "context_build"}).status_code == 403
    missing = user_client.post(runs, json={"operation": "context_build", "catalog": "template", "template_name": "x"})
    assert missing.json()["code"] == "context_build_invalid"
    no_manifest = user_client.post(runs, json={"operation": "context_build", "catalog": "manifest"})
    assert no_manifest.json()["code"] == "context_build_invalid"
    assert user_client.post(runs, json={"operation": "context_build", "catalog": "domains"}).status_code == 422

    queued = user_client.post(
        runs,
        json={
            "operation": "context_build",
            "catalog": "template",
            "template_name": "obras",
            "template_markdown": "lo que mande el cliente",
        },
    )
    assert queued.status_code == 202, queued.text
    body = queued.json()
    assert body["is_write"] is True and "template_markdown" not in body["params"]
    assert body["params"]["output_folder_name"] == "organizado"
    stored = db.get(Run, body["id"])
    assert stored is not None and stored.params["template_markdown"] == TEMPLATE


def test_build_folder_is_validated_and_then_fixed(
    user_client: TestClient, project: dict[str, object], db: Session
) -> None:
    runs = f"/api/v1/projects/{project['id']}/runs"
    for reserved in ("Conversión", "duplicados", "site", "../fuera"):
        response = user_client.post(runs, json={"operation": "context_build", "output_folder_name": reserved})
        assert response.json()["code"] == "context_build_invalid", reserved
    _seed_context(db, int(str(project["id"])))

    other = user_client.post(runs, json={"operation": "context_build", "output_folder_name": "otra"})
    assert other.json()["code"] == "context_build_invalid"


def test_build_needs_a_writable_destination(user_client: TestClient, project: dict[str, object], db: Session) -> None:
    db.execute(update(Location).where(Location.name == "Salidas").values(access="ro"))
    db.commit()
    response = user_client.post(f"/api/v1/projects/{project['id']}/runs", json={"operation": "context_build"})
    assert response.json()["code"] == "location_read_only"


def test_delete_is_for_owners_with_a_preview(
    user_client: TestClient, project: dict[str, object], db: Session, make_user: Callable[..., User]
) -> None:
    runs = f"/api/v1/projects/{project['id']}/runs"
    editor = _member(user_client, project["id"], make_user, "editora", "editor")
    assert editor.post(runs, json={"operation": "context_delete"}).status_code == 403

    preview = user_client.post(runs, json={"operation": "context_delete"}).json()
    assert preview["params"]["dry_run"] is True and preview["is_write"] is False
    real = {"operation": "context_delete", "dry_run": False, "preview_run_id": preview["id"]}
    assert user_client.post(runs, json=real | {"confirm_name": "Proyecto A"}).json()["code"] == "preview_required"
    db.execute(update(Run).where(Run.id == preview["id"]).values(status="succeeded", finished_at=utcnow()))
    db.commit()
    assert user_client.post(runs, json=real | {"confirm_name": "otro"}).json()["code"] == "preview_required"
    assert user_client.post(runs, json=real | {"confirm_name": "Proyecto A"}).status_code == 202


# --- sitio aislado ---------------------------------------------------------------------------------------------------


def _write_site(migrated: Settings) -> Path:
    root = migrated.locations_root / "salidas" / "Proyecto A" / "site"
    (root / "facturas").mkdir(parents=True)
    (root / "index.html").write_text("<h1>Inicio</h1>", encoding="utf-8")
    (root / "facturas" / "index.html").write_text("<h1>Facturas</h1>", encoding="utf-8")
    (root / "app.js").write_text("console.log(1)", encoding="utf-8")
    (root / "datos.bin").write_bytes(b"\x00\x01")
    return root


def _site_url(client: TestClient, project_id: object) -> str:
    response = client.post(f"/api/v1/projects/{project_id}/context/site-session")
    assert response.status_code == 200, response.text
    return str(response.json()["url"])


def test_site_is_served_with_its_own_sandbox(
    user_client: TestClient, project: dict[str, object], db: Session, migrated: Settings
) -> None:
    assert user_client.post(f"/api/v1/projects/{project['id']}/context/site-session").json()["code"] == (
        "site_not_found"
    )
    _seed_context(db, int(str(project["id"])))
    _write_site(migrated)
    url = _site_url(user_client, project["id"])
    anonymous = TestClient(user_client.app, base_url="https://testserver")

    index = anonymous.get(url)
    folder = anonymous.get(f"{url}facturas/")
    script = anonymous.get(f"{url}app.js")
    binary = anonymous.get(f"{url}datos.bin")

    assert url.startswith("/site/") and url.endswith("/")
    assert index.status_code == 200 and index.text == "<h1>Inicio</h1>"
    assert index.headers["content-type"].startswith("text/html")
    csp = index.headers["content-security-policy"]
    assert csp.startswith("sandbox allow-scripts") and "allow-same-origin" not in csp
    assert "frame-ancestors 'self'" in csp
    assert index.headers["x-frame-options"] == "SAMEORIGIN"
    assert index.headers["referrer-policy"] == "no-referrer"
    assert "allow-popups-to-escape-sandbox" not in csp
    assert index.headers["cache-control"] == "no-store"
    assert index.headers["cross-origin-opener-policy"] == "unsafe-none"
    assert folder.text == "<h1>Facturas</h1>"
    assert script.headers["content-type"].startswith("text/javascript")
    assert binary.headers["content-type"] == "application/octet-stream"
    assert "attachment" in binary.headers["content-disposition"]
    redirect = anonymous.get(url.rstrip("/"), follow_redirects=False)
    assert redirect.status_code == 308 and redirect.headers["location"] == url


def test_site_rejects_bad_tokens_and_paths(
    user_client: TestClient, project: dict[str, object], db: Session, migrated: Settings
) -> None:
    _seed_context(db, int(str(project["id"])))
    _write_site(migrated)
    (migrated.locations_root / "salidas" / "Proyecto A" / "secreto.txt").write_text("x", encoding="utf-8")
    url = _site_url(user_client, project["id"])
    project_id, session_id, expires, signature = url.split("/")[2].split(".")
    forged = f"/site/{project_id}.{session_id}.{int(expires) + 60}.{signature}/"
    other_project = f"/site/{int(project_id) + 1}.{session_id}.{expires}.{signature}/"

    for bad in (forged, other_project, "/site/basura/", "/site/1.2.3.abc/"):
        response = user_client.get(bad)
        assert response.status_code == 404, bad
        assert "sandbox" in response.headers["content-security-policy"]
    assert user_client.get(f"{url}../secreto.txt").status_code == 404
    assert user_client.get(f"{url}%2e%2e/secreto.txt").status_code == 404
    assert user_client.get(f"{url}no-existe.html").status_code == 404


def test_site_token_dies_with_the_session_and_expires(
    user_client: TestClient, project: dict[str, object], db: Session, migrated: Settings
) -> None:
    _seed_context(db, int(str(project["id"])))
    _write_site(migrated)
    url = _site_url(user_client, project["id"])
    assert user_client.get(url).status_code == 200

    db.execute(update(UserSession).values(expires_at=utcnow() - timedelta(seconds=1)))
    db.commit()
    assert user_client.get(url).status_code == 404


def test_site_token_is_bound_to_the_session_hash(
    user_client: TestClient, project: dict[str, object], db: Session, migrated: Settings
) -> None:
    _seed_context(db, int(str(project["id"])))
    _write_site(migrated)
    url = _site_url(user_client, project["id"])
    # La misma fila de sesión con otro token (id reutilizado) invalida el token del sitio.
    db.execute(update(UserSession).values(token_hash="f" * 64))
    db.commit()
    assert site.SITE_TOKEN_TTL <= timedelta(hours=1)
    assert TestClient(user_client.app, base_url="https://testserver").get(url).status_code == 404


def test_site_token_stops_working_for_removed_members(
    user_client: TestClient,
    project: dict[str, object],
    db: Session,
    migrated: Settings,
    make_user: Callable[..., User],
) -> None:
    _seed_context(db, int(str(project["id"])))
    _write_site(migrated)
    viewer = _member(user_client, project["id"], make_user, "lectora", "viewer")
    url = _site_url(viewer, project["id"])
    assert viewer.get(url).status_code == 200
    lectora = db.scalars(select(User).where(User.username == "lectora")).one()
    assert user_client.delete(f"/api/v1/projects/{project['id']}/members/{lectora.id}").status_code == 204
    assert viewer.get(url).status_code == 404


@pytest.mark.skipif(sys.platform == "win32", reason="enlaces simbólicos")
def test_site_does_not_follow_links(
    user_client: TestClient, project: dict[str, object], db: Session, migrated: Settings, tmp_path: Path
) -> None:
    _seed_context(db, int(str(project["id"])))
    root = _write_site(migrated)
    secret = tmp_path / "secreto.html"
    secret.write_text("secreto", encoding="utf-8")
    os.symlink(secret, root / "enlace.html")
    url = _site_url(user_client, project["id"])

    assert user_client.get(f"{url}enlace.html").status_code == 404
    # La propia carpeta del sitio cambiada por un enlace tampoco se sirve.
    other = tmp_path / "otro-sitio"
    other.mkdir()
    (other / "index.html").write_text("ajeno", encoding="utf-8")
    for child in root.iterdir():
        if child.is_dir() and not child.is_symlink():
            for f in child.iterdir():
                f.unlink()
            child.rmdir()
        else:
            child.unlink()
    root.rmdir()
    root.symlink_to(other)
    assert user_client.get(url).status_code == 404


def test_site_token_is_not_logged(
    user_client: TestClient,
    project: dict[str, object],
    db: Session,
    migrated: Settings,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _seed_context(db, int(str(project["id"])))
    _write_site(migrated)
    url = _site_url(user_client, project["id"])
    token = url.split("/")[2]
    with caplog.at_level("INFO", logger="app.access"):
        user_client.get(f"{url}index.html")
    paths = [getattr(r, "path", "") for r in caplog.records if r.name == "app.access"]
    assert "/site/***/index.html" in paths
    assert all(token not in p for p in paths)
