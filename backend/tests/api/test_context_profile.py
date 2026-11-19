"""Perfil del proyecto y vista previa del prompt (W3; doc_organize 2.0, G2 y D11): permisos, ``If-Match``, escritura
sin seguir enlaces, auditoría sin el texto y la vista previa sin llamar al modelo. Datos sintéticos."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import AuditEntry, Location, User
from tests.api.test_context import TEMPLATE
from tests.conftest import ADMIN_PASSWORD, login_as, project_payload

PROFILE = """# Perfil sintético

## Contexto del proyecto
Documentación sintética de una obra de prueba.

## Glosario
- POB: plan de obra sintético.

## Ejemplos
- «Factura de enero» → facturas
"""
TEMPLATE_WITH_PROFILE = TEMPLATE + "\n## Reglas de desempate\nUna factura es siempre de facturas.\n"


@pytest.fixture
def project(user_client: TestClient, project_locations: dict[str, Location]) -> dict[str, object]:
    response = user_client.post("/api/v1/projects", json=project_payload(project_locations))
    assert response.status_code == 201, response.text
    return dict(response.json())


@pytest.fixture
def url(project: dict[str, object]) -> str:
    return f"/api/v1/projects/{project['id']}/context/profile"


@pytest.fixture
def target(migrated: Settings) -> Path:
    return migrated.locations_root / "salidas" / "Proyecto A" / ".doc_organize" / "profile.md"


def _etag(client: TestClient, url: str) -> str:
    return str(client.get(url).json()["etag"])


def test_profile_is_saved_read_and_deleted_by_editors(
    user_client: TestClient,
    url: str,
    target: Path,
    project: dict[str, object],
    make_user: Callable[..., User],
    db: Session,
) -> None:
    viewer_user = make_user("lectora")
    user_client.post(f"/api/v1/projects/{project['id']}/members", json={"user_id": viewer_user.id, "role": "viewer"})
    viewer = login_as(user_client, "lectora")

    empty = user_client.get(url).json()
    assert empty == {"markdown": None, "sections": None, "etag": "none"}
    assert viewer.put(url, json={"markdown": PROFILE}, headers={"If-Match": "none"}).status_code == 403
    assert user_client.put(url, json={"markdown": PROFILE}).json()["code"] == "etag_required"

    saved = user_client.put(url, json={"markdown": PROFILE}, headers={"If-Match": "none"})

    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert target.read_text(encoding="utf-8") == PROFILE
    assert body["sections"]["context"] == "Documentación sintética de una obra de prueba."
    assert body["sections"]["examples"] == ["«Factura de enero» → facturas"]
    assert viewer.get(url).json()["markdown"] == PROFILE  # leer: cualquier miembro
    stale = user_client.put(url, json={"markdown": PROFILE + "x"}, headers={"If-Match": "none"})
    assert stale.status_code == 409 and stale.json()["code"] == "profile_changed"
    entry = db.scalars(select(AuditEntry).where(AuditEntry.action == "project.profile_save")).one()
    assert entry.details == {"sections": ["context", "glossary", "examples"]}
    assert "sintética" not in json.dumps(entry.details)  # nunca el texto

    deleted = user_client.delete(url, headers={"If-Match": body["etag"]})
    assert deleted.status_code == 200 and deleted.json()["markdown"] is None and not target.exists()
    assert db.scalars(select(AuditEntry).where(AuditEntry.action == "project.profile_delete")).one()


def test_profile_limits(user_client: TestClient, url: str) -> None:
    too_big = user_client.put(url, json={"markdown": "x" * 40_000}, headers={"If-Match": "none"})
    assert too_big.status_code == 422


@pytest.mark.skipif(sys.platform == "win32", reason="enlaces simbólicos sin privilegios solo en POSIX")
def test_profile_never_follows_links(user_client: TestClient, url: str, target: Path, tmp_path: Path) -> None:
    outside = tmp_path / "fuera.md"
    outside.write_text("ajeno", encoding="utf-8")
    target.parent.mkdir(parents=True)
    os.symlink(outside, target)

    response = user_client.put(url, json={"markdown": PROFILE}, headers={"If-Match": "none"})

    assert response.status_code == 409 and response.json()["code"] == "profile_replaced"
    assert outside.read_text(encoding="utf-8") == "ajeno"


def test_prompt_preview_composes_template_and_project_profiles(
    user_client: TestClient, url: str, project: dict[str, object], admin: User
) -> None:
    """D11: el perfil del proyecto (o el borrador del formulario) se añade detrás del de la plantilla."""
    admin_client = login_as(user_client, admin.username, ADMIN_PASSWORD)
    assert admin_client.put("/api/v1/taxonomy-templates/obras", json={"markdown": TEMPLATE_WITH_PROFILE}).status_code
    user_client.put(url, json={"markdown": PROFILE}, headers={"If-Match": "none"})
    preview_url = f"/api/v1/projects/{project['id']}/context/prompt-preview"

    saved = user_client.post(preview_url, json={"catalog": "template", "template_name": "obras"})
    draft = user_client.post(
        preview_url,
        json={"catalog": "template", "template_name": "obras", "profile_markdown": "## Glosario\n- XYZ: borrador.\n"},
    )

    assert saved.status_code == 200, saved.text
    body = saved.json()
    system = body["messages"][0]["content"]
    assert body["messages"][0]["role"] == "system" and "facturas" in system
    assert "Una factura es siempre de facturas." in system and "Documentación sintética" in system
    assert body["template_profile"]["tie_breakers"] == "Una factura es siempre de facturas."
    assert body["project_profile"]["context"] == "Documentación sintética de una obra de prueba."
    assert "XYZ: borrador." in draft.json()["messages"][0]["content"]
    assert "Documentación sintética" not in draft.json()["messages"][0]["content"]  # el borrador sustituye al guardado
    no_manifest = user_client.post(preview_url, json={"catalog": "manifest"})
    assert no_manifest.status_code == 422 and no_manifest.json()["code"] == "prompt_preview_invalid"


def test_template_preview_needs_templates_manage(user_client: TestClient, admin: User) -> None:
    preview_url = "/api/v1/taxonomy-templates/prompt-preview"
    assert user_client.post(preview_url, json={"markdown": TEMPLATE_WITH_PROFILE}).status_code == 403
    admin_client = login_as(user_client, admin.username, ADMIN_PASSWORD)

    response = admin_client.post(preview_url, json={"markdown": TEMPLATE_WITH_PROFILE})

    assert response.status_code == 200, response.text
    assert response.json()["profile"]["tie_breakers"] == "Una factura es siempre de facturas."
    assert admin_client.post(preview_url, json={"markdown": "no"}).json()["code"] == "template_invalid"
