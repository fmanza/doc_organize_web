"""Versiones de un documento (W6, doc_organize 2.0 F5): el ajuste del proyecto llega a ``build(versions=)``; la
construcción guarda los grupos (con rutas relativas), marca la versión antigua, la deja fuera con ``current_only`` y
respeta la vigente que decide una persona. Documentos sintéticos con marcador de versión en el nombre."""

from __future__ import annotations

import json
import time
from typing import Any

import pytest
from doc_organize import CacheEntry, ConversionStatus, DocumentStatus
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import AuditEntry, ContextDocument, Project, ProjectContext
from app.domain.documents.outputs import output_paths
from app.domain.projects.service import state_dir
from app.domain.scan.state import CONVERSION_DIR, folder_cache
from app.jobs.operations import context as operation
from tests.api.test_documents import write_cache
from tests.conftest import ADMIN_PASSWORD, login_as
from tests.jobs.test_context_axes import AXES_TEMPLATE
from tests.jobs.test_context_operation import FILES, _finish

VERSIONS = [
    ("2024", "plan v1.txt", "Plan de obra v1", "plan de obra primera"),
    ("2024", "plan v2.txt", "Plan de obra v2", "plan de obra segunda"),
]
TEMPLATE_RUN = {"operation": "context_build", "catalog": "template", "template_name": "ejes", "build_site": False}


@pytest.fixture
def versioned(project: Project, migrated: Settings, user_client: TestClient, admin: Any) -> Project:
    """El proyecto de prueba con dos versiones del mismo documento, convertidas y en la caché de 2024."""
    source = (migrated.locations_root / "origen").resolve()
    conversion = migrated.locations_root / "salidas" / "Proyecto A" / CONVERSION_DIR
    for folder, relative, title, text in VERSIONS:
        (source / folder / relative).write_text(text, encoding="utf-8")
        paths = output_paths(folder, relative)
        (conversion / paths.markdown).parent.mkdir(parents=True, exist_ok=True)
        (conversion / paths.markdown).write_text(f"# {title}\n\n{text}\n", encoding="utf-8")
        (conversion / paths.json).write_text(json.dumps({"title": title, "chunks": [{"text": text}]}), encoding="utf-8")
    entries = [
        CacheEntry(
            file_path=str(source / f / r),
            sha256_hash=str(i) * 64,
            timestamp=time.time(),
            status=DocumentStatus.NEW,
            conversion_status=ConversionStatus.SUCCESS,
        )
        for i, (f, r, _, _) in enumerate([*FILES, *VERSIONS])
        if f == "2024"
    ]
    write_cache(folder_cache(state_dir(migrated, project.id), "2024"), entries)
    admin_client = login_as(user_client, admin.username, ADMIN_PASSWORD)
    assert admin_client.put("/api/v1/taxonomy-templates/ejes", json={"markdown": AXES_TEMPLATE}).status_code == 201
    return project


def _set(db: Session, project: Project, mode: str) -> None:
    db.execute(update(Project).where(Project.id == project.id).values(context_versions=mode))
    db.commit()
    project.context_versions = mode  # el worker lo lee de la BD; el de la fixture está desligado


def _docs(db: Session, project: Project) -> dict[str, ContextDocument]:
    rows = db.scalars(select(ContextDocument).where(ContextDocument.project_id == project.id))
    return {f"{d.folder}/{d.path}": d for d in rows}


@pytest.mark.posix_paths
def test_mark_groups_versions_and_filters_the_current_ones(
    run: Any, versioned: Project, db: Session, user_client: TestClient, migrated: Settings
) -> None:
    assert user_client.get(f"/api/v1/projects/{versioned.id}").json()["context_versions"] == "mark"  # D8
    ctx, params = run(TEMPLATE_RUN)

    operation.run_build(ctx, params, versioned)

    stored = db.get(ProjectContext, versioned.id)
    assert stored is not None and stored.versions_mode == "mark"
    (group,) = stored.version_groups
    assert group["members"] == ["2024/plan v1.txt", "2024/plan v2.txt"] and group["versions"] == ["1", "2"]
    assert group["current"] == "2024/plan v2.txt" and group["confirmed"] is False
    assert str(migrated.locations_root) not in json.dumps(stored.version_groups)
    docs = _docs(db, versioned)
    assert docs["2024/plan v1.txt"].is_current is False and docs["2024/plan v2.txt"].is_current is True
    url = f"/api/v1/projects/{versioned.id}/context/documents"
    domain = docs["2024/plan v1.txt"].domain_slug
    every = user_client.get(url, params={"domain": domain} if domain else {}).json()
    current = user_client.get(url, params={"current": True, **({"domain": domain} if domain else {})}).json()
    assert current["total"] == every["total"] - 1
    assert "plan v1.txt" not in [d["path"] for d in current["items"]]
    body = user_client.get(f"/api/v1/projects/{versioned.id}/context").json()
    assert body["version_groups"][0]["current"] == "2024/plan v2.txt"


@pytest.mark.posix_paths
def test_current_only_leaves_the_old_version_out(run: Any, versioned: Project, db: Session) -> None:
    _set(db, versioned, "current_only")
    ctx, params = run(TEMPLATE_RUN)

    operation.run_build(ctx, params, versioned)

    docs = _docs(db, versioned)
    assert "2024/plan v1.txt" not in docs and "2024/plan v2.txt" in docs
    stored = db.get(ProjectContext, versioned.id)
    assert stored is not None and stored.superseded == ["2024/plan v1.txt"] and stored.superseded_count == 1


@pytest.mark.posix_paths
def test_a_person_confirms_the_current_version(
    run: Any, versioned: Project, db: Session, user_client: TestClient
) -> None:
    ctx, params = run(TEMPLATE_RUN)
    operation.run_build(ctx, params, versioned)
    _finish(db, ctx)
    review = user_client.get(
        f"/api/v1/projects/{versioned.id}/context/review", params={"reason": "unconfirmed_version"}
    )
    assert review.json()["total"] == 1
    decided = user_client.post(
        f"/api/v1/projects/{versioned.id}/context/decisions",
        json={"document_key": "2024/plan v1.txt", "action": "set_current_version"},
    )
    assert decided.status_code == 201, decided.text

    ctx2, params2 = run(TEMPLATE_RUN)
    operation.run_build(ctx2, params2, versioned)

    stored = db.get(ProjectContext, versioned.id)
    assert stored is not None
    (group,) = stored.version_groups
    assert group["current"] == "2024/plan v1.txt" and group["confirmed"] is True
    assert _docs(db, versioned)["2024/plan v1.txt"].is_current is True


def test_settings_api(versioned: Project, user_client: TestClient, db: Session) -> None:
    url = f"/api/v1/projects/{versioned.id}/ai-settings"

    response = user_client.put(url, json={"context_versions": "current_only"})
    invalid = user_client.put(url, json={"context_versions": "otra"})

    assert response.status_code == 200 and response.json()["context_versions"] == "current_only"
    assert response.json()["ai_redact_credentials"] is True  # lo que no se manda no cambia
    assert invalid.status_code == 422
    entry = db.scalars(select(AuditEntry).where(AuditEntry.action == "project.ai_settings_update")).one()
    assert entry.details == {"context_versions": ["mark", "current_only"]}


@pytest.mark.posix_paths
def test_versions_across_formats_when_the_project_asks(
    run: Any, versioned: Project, db: Session, migrated: Settings, user_client: TestClient
) -> None:
    """2.5.0: con la casilla, ``plan v3.docx`` es la versión siguiente de los ``.txt`` y la construcción lo registra."""
    source = (migrated.locations_root / "origen").resolve()
    conversion = migrated.locations_root / "salidas" / "Proyecto A" / CONVERSION_DIR
    (source / "2024" / "plan v3.docx").write_text("plan de obra tercera", encoding="utf-8")
    paths = output_paths("2024", "plan v3.docx")
    (conversion / paths.markdown).write_text("# Plan de obra v3\n\nplan de obra tercera\n", encoding="utf-8")
    (conversion / paths.json).write_text(
        json.dumps({"title": "Plan de obra v3", "chunks": [{"text": "plan"}]}), encoding="utf-8"
    )
    cache = folder_cache(state_dir(migrated, versioned.id), "2024")
    entry = CacheEntry(
        file_path=str(source / "2024" / "plan v3.docx"),
        sha256_hash="9" * 64,
        timestamp=time.time(),
        status=DocumentStatus.NEW,
        conversion_status=ConversionStatus.SUCCESS,
    )
    write_cache(cache, [entry])  # se añade a la caché de la fixture
    assert (
        user_client.put(
            f"/api/v1/projects/{versioned.id}/ai-settings", json={"context_versions_across_extensions": True}
        ).status_code
        == 200
    )
    ctx, params = run(TEMPLATE_RUN)

    operation.run_build(ctx, params, versioned)

    stored = db.get(ProjectContext, versioned.id)
    assert stored is not None and stored.versions_across_extensions is True
    (group,) = stored.version_groups
    assert group["current"] == "2024/plan v3.docx" and group["versions"] == ["1", "2", "3"]
    assert user_client.get(f"/api/v1/projects/{versioned.id}/context").json()["versions_across_extensions"] is True


def test_across_formats_setting_api(versioned: Project, user_client: TestClient, db: Session) -> None:
    url = f"/api/v1/projects/{versioned.id}/ai-settings"
    assert user_client.get(f"/api/v1/projects/{versioned.id}").json()["context_versions_across_extensions"] is False

    response = user_client.put(url, json={"context_versions_across_extensions": True})

    assert response.status_code == 200 and response.json()["context_versions_across_extensions"] is True
    entry = db.scalars(select(AuditEntry).where(AuditEntry.action == "project.ai_settings_update")).one()
    assert entry.details == {"context_versions_across_extensions": [False, True]}
