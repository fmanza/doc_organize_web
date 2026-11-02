"""Documentos, visor de salidas y búsqueda (Fase 5) en la API, con cachés reales de doc_organize (``CacheManager``)
y un índice FTS5 real. Las exportaciones como runs: lanzar (roles y parámetros); el trabajo, en
``tests/jobs/test_export_operation.py``."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from collections.abc import Callable
from pathlib import Path

import pytest
from doc_organize import CacheEntry, CacheManager
from doc_organize.core.models import ConversionStatus, DocumentStatus
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.models import Location, User
from app.domain.documents import service as documents
from app.domain.projects.service import state_dir
from app.domain.scan.state import CONVERSION_DIR, folder_cache
from app.domain.search.index import reindex, search_db
from tests.conftest import login_as, project_payload


def write_cache(cache_db: Path, entries: list[CacheEntry]) -> None:
    """Caché de doc_organize con ``entries`` (como la deja un escaneo)."""
    cache_db.parent.mkdir(parents=True, exist_ok=True)

    async def _save() -> None:
        async with CacheManager(cache_db) as cache:
            await cache.save_entries(entries)

    asyncio.run(_save())


def entry(path: Path, *, status: str = "success", error: str | None = None) -> CacheEntry:
    return CacheEntry(
        file_path=str(path),
        sha256_hash="0" * 64,
        timestamp=time.time(),
        status=DocumentStatus.NEW,
        conversion_status=ConversionStatus(status),
        error_message=error,
        error_retry_count=1 if error else 0,
    )


@pytest.fixture
def project(user_client: TestClient, project_locations: dict[str, Location], migrated: Settings) -> dict[str, object]:
    response = user_client.post(
        "/api/v1/projects", json=project_payload(project_locations, source_subpaths=["2024", "2025"])
    )
    assert response.status_code == 201, response.text
    body = dict(response.json())
    source = Path(project_locations["source"].container_path)
    state = state_dir(migrated, int(body["id"]))  # type: ignore[arg-type]
    write_cache(
        folder_cache(state, "2024"),
        [
            entry(source / "2024" / "factura.txt"),
            entry(source / "2024" / "facturas" / "enero .pdf"),
            entry(source / "2024" / "roto.pdf", status="error", error=f"No se pudo abrir {source}/2024/roto.pdf"),
        ],
    )
    write_cache(folder_cache(state, "2025"), [entry(source / "2025" / "Café.docx")])
    return body


def conversion(migrated: Settings) -> Path:
    path = migrated.locations_root / "salidas" / "Proyecto A" / CONVERSION_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


# --- documentos --------------------------------------------------------------------------------------------------


def test_documents_span_the_caches_of_all_folders(
    user_client: TestClient, project: dict[str, object], migrated: Settings
) -> None:
    base = f"/api/v1/projects/{project['id']}/documents"

    first = user_client.get(base, params={"limit": 2}).json()
    second = user_client.get(base, params={"limit": 2, "offset": 2}).json()

    assert first["total"] == second["total"] == 4
    rows = first["items"] + second["items"]
    assert [(r["folder"], r["path"]) for r in rows] == [
        ("2024", "factura.txt"),
        ("2024", "facturas/enero .pdf"),
        ("2024", "roto.pdf"),
        ("2025", "Café.docx"),
    ]
    assert rows[1]["output_path"] == "2024/facturas/enero.md"
    assert rows[2]["output_path"] is None and rows[2]["error_message"] == "No se pudo abrir «Origen»/2024/roto.pdf"
    assert str(migrated.locations_root) not in str(rows)


def test_documents_search_and_folder_filter(user_client: TestClient, project: dict[str, object]) -> None:
    base = f"/api/v1/projects/{project['id']}/documents"

    found = user_client.get(base, params={"search": "CAFÉ"}).json()
    only_2024 = user_client.get(base, params={"folder": "2024"}).json()
    unknown = user_client.get(base, params={"folder": "otra"})

    assert [r["path"] for r in found["items"]] == ["Café.docx"] and found["total"] == 1
    # G22: la búsqueda mira la ruta relativa a la carpeta, no la del servidor («origen» es la carpeta de la ubicación).
    assert user_client.get(base, params={"search": "origen"}).json()["total"] == 0
    errors = user_client.get(base, params={"conversion_status": "error"}).json()
    assert [r["path"] for r in errors["items"]] == ["roto.pdf"] and errors["total"] == 1
    assert user_client.get(base, params={"conversion_status": "otro"}).status_code == 422
    assert only_2024["total"] == 3
    assert unknown.status_code == 422 and unknown.json()["code"] == "folder_not_saved"


def test_documents_need_membership(
    user_client: TestClient, project: dict[str, object], make_user: Callable[..., User]
) -> None:
    make_user("lectora")
    reader_user = make_user("otra")
    assert (
        user_client.post(
            f"/api/v1/projects/{project['id']}/members", json={"user_id": reader_user.id, "role": "viewer"}
        ).status_code
        == 201
    )

    assert login_as(user_client, "otra").get(f"/api/v1/projects/{project['id']}/documents").status_code == 200
    assert login_as(user_client, "lectora").get(f"/api/v1/projects/{project['id']}/documents").status_code == 404


def test_project_without_scan_has_no_documents(user_client: TestClient, project_locations: dict[str, Location]) -> None:
    created = user_client.post("/api/v1/projects", json=project_payload(project_locations, name="Nuevo")).json()

    assert user_client.get(f"/api/v1/projects/{created['id']}/documents").json() == {"items": [], "total": 0}


# --- visor -------------------------------------------------------------------------------------------------------


def test_output_is_served_with_a_fixed_type(
    user_client: TestClient, project: dict[str, object], migrated: Settings
) -> None:
    folder = conversion(migrated) / "2024" / "facturas"
    folder.mkdir(parents=True)
    (folder / "enero.md").write_text("# Enero\n\n<script>alert(1)</script>", encoding="utf-8")
    (folder / "img" / "enero").mkdir(parents=True)
    (folder / "img" / "enero" / "p1.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    md = user_client.get(f"/api/v1/projects/{project['id']}/outputs", params={"path": "2024/facturas/enero.md"})
    png = user_client.get(
        f"/api/v1/projects/{project['id']}/outputs", params={"path": "2024/facturas/img/enero/p1.png"}
    )

    assert md.status_code == 200 and md.text.startswith("# Enero")
    assert md.headers["content-type"] == "text/markdown; charset=utf-8"
    assert md.headers["x-content-type-options"] == "nosniff"
    assert md.headers["content-security-policy"].startswith("default-src 'none'")
    assert md.headers["cache-control"] == "private, no-store"
    assert png.headers["content-type"] == "image/png"


def test_json_output_hides_the_container_path(
    user_client: TestClient, project: dict[str, object], migrated: Settings
) -> None:
    folder = conversion(migrated) / "2024"
    folder.mkdir()
    source = migrated.locations_root / "origen" / "2024" / "factura.txt"
    (folder / "factura.json").write_text(json.dumps({"source_path": str(source), "title": "factura"}), encoding="utf-8")

    response = user_client.get(f"/api/v1/projects/{project['id']}/outputs", params={"path": "2024/factura.json"})

    assert response.status_code == 200 and response.headers["content-type"] == "application/json"
    assert response.json() == {"source_path": "2024/factura.txt", "title": "factura"}
    # Desde doc_organize 0.12.0 (G23) la ruta ya viene relativa a la carpeta escaneada: se le antepone la carpeta.
    (folder / "nota.json").write_text(json.dumps({"source_path": "notas/nota.html"}), encoding="utf-8")
    relative = user_client.get(f"/api/v1/projects/{project['id']}/outputs", params={"path": "2024/nota.json"})
    assert relative.json() == {"source_path": "2024/notas/nota.html"}
    assert response.headers["x-content-type-options"] == "nosniff"


def test_output_rejects_paths_types_and_sizes(
    user_client: TestClient, project: dict[str, object], migrated: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = conversion(migrated)
    (root / "2024").mkdir()
    (root / "2024" / "dibujo.svg").write_text("<svg onload='alert(1)'/>", encoding="utf-8")
    (root / "2024" / "grande.md").write_text("x" * 100, encoding="utf-8")
    (migrated.locations_root / "salidas" / "Proyecto A" / "fuera.md").write_text("secreto", encoding="utf-8")
    base = f"/api/v1/projects/{project['id']}/outputs"
    monkeypatch.setattr(documents, "MAX_OUTPUT_BYTES", 10)

    assert user_client.get(base, params={"path": "../fuera.md"}).status_code == 400
    assert user_client.get(base, params={"path": "/etc/passwd.md"}).status_code == 400
    assert user_client.get(base, params={"path": "2024/dibujo.svg"}).json()["code"] == "output_type_not_allowed"
    assert user_client.get(base, params={"path": "2024/no-existe.md"}).json()["code"] == "output_not_found"
    assert user_client.get(base, params={"path": "2024/grande.md"}).json()["code"] == "output_too_large"


@pytest.mark.skipif(sys.platform == "win32", reason="enlaces simbólicos")
def test_output_does_not_follow_links_outside(
    user_client: TestClient, project: dict[str, object], migrated: Settings
) -> None:
    root = conversion(migrated)
    secret = migrated.locations_root / "origen" / "2024" / "secreto.md"
    secret.write_text("no", encoding="utf-8")
    os.symlink(secret, root / "enlace.md")

    response = user_client.get(f"/api/v1/projects/{project['id']}/outputs", params={"path": "enlace.md"})

    assert response.status_code == 404


# --- búsqueda ----------------------------------------------------------------------------------------------------


def test_search_finds_words_in_the_converted_markdown(
    user_client: TestClient, project: dict[str, object], migrated: Settings
) -> None:
    root = conversion(migrated)
    (root / "2024").mkdir()
    (root / "2025").mkdir()
    (root / "2024" / "factura.md").write_text("# Factura de enero\n\nImporte de la luz: 120 euros.", encoding="utf-8")
    (root / "2025" / "acta.md").write_text("# Acta\n\nReunión sobre la luz del portal.", encoding="utf-8")
    base = f"/api/v1/projects/{project['id']}/search"

    before = user_client.get(base, params={"q": "luz"}).json()
    reindex(search_db(state_dir(migrated, int(project["id"]))), root)  # type: ignore[arg-type]
    both = user_client.get(base, params={"q": "luz"}).json()
    accents = user_client.get(base, params={"q": "reunion"}).json()
    in_2024 = user_client.get(base, params={"q": "luz", "folder": "2024"}).json()
    syntax = user_client.get(base, params={"q": 'luz OR "portal NEAR( title:*'})

    assert before == {"items": [], "total": 0, "indexed_at": None}
    assert both["total"] == 2 and both["indexed_at"] is not None
    assert {h["output_path"] for h in both["items"]} == {"2024/factura.md", "2025/acta.md"}
    assert "\u0002luz\u0003" in both["items"][0]["snippet"]
    assert [h["title"] for h in accents["items"]] == ["Acta"]
    assert [h["output_path"] for h in in_2024["items"]] == ["2024/factura.md"]
    assert syntax.status_code == 200
    assert user_client.get(base, params={"q": "luz", "folder": "otra"}).json()["code"] == "folder_not_saved"
    assert user_client.get(base, params={"q": ""}).status_code == 422


# --- exportaciones como runs -------------------------------------------------------------------------------------


def test_any_member_exports_but_only_editors_reindex(
    user_client: TestClient, project: dict[str, object], make_user: Callable[..., User]
) -> None:
    reader_user = make_user("lector")
    user_client.post(f"/api/v1/projects/{project['id']}/members", json={"user_id": reader_user.id, "role": "viewer"})
    reader = login_as(user_client, "lector")
    runs = f"/api/v1/projects/{project['id']}/runs"

    preview = reader.post(runs, json={"operation": "export_zip", "dry_run": True})
    xlsx = reader.post(runs, json={"operation": "export_xlsx", "kind": "errors"})
    bad_kind = reader.post(runs, json={"operation": "export_xlsx", "kind": "todo"})
    reindex_reader = reader.post(runs, json={"operation": "search_index"})
    reindex_owner = user_client.post(runs, json={"operation": "search_index"})

    assert preview.status_code == 202 and preview.json()["params"]["dry_run"] is True
    assert xlsx.status_code == 202 and xlsx.json()["queue"] == "cpu"
    assert bad_kind.status_code == 422
    assert reindex_reader.status_code == 403
    assert reindex_owner.status_code == 202
    # Reindexar escribe search.db: no coincide con un escaneo (que también reindexa al terminar).
    assert user_client.post(runs, json={"operation": "scan"}).json()["code"] == "write_locked"
