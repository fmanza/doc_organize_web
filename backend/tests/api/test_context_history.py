"""web 1.5.0 (doc_organize 1.5.0): historial del contexto en la API (``GET /projects/{id}/context/history``).

El historial vive en la carpeta del proyecto en el destino (``historial_contexto/CONTEXT_HISTORY.jsonl``) y se conserva
al borrar el contexto. Aquí se escribe a mano con ``ContextBuildRecord`` de doc_organize.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from doc_organize import ContextBuildRecord, ContextChange
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.domain.context import service as context_service
from tests.api.test_context import project  # noqa: F401  (fixture)


def _history(migrated: Settings) -> Path:
    return migrated.locations_root / "salidas" / "Proyecto A" / "historial_contexto" / "CONTEXT_HISTORY.jsonl"


def _record(built_at: str, *changes: ContextChange, classified: int = 2) -> str:
    record = ContextBuildRecord(
        built_at=built_at,
        project_name="Proyecto A",
        built_with_version="1.5.0",
        ai_classification_model="clasificador" if changes else None,
        classified=classified,
        unclassified=1,
        changes=list(changes),
    )
    return record.model_dump_json()


def _source(migrated: Settings, relative: str) -> str:
    return str((migrated.locations_root / "origen").resolve() / relative)


def _url(target: dict[str, object]) -> str:
    return f"/api/v1/projects/{target['id']}/context/history"


def test_without_history_it_is_empty(user_client: TestClient, project: dict[str, object]) -> None:  # noqa: F811
    response = user_client.get(_url(project))

    assert response.status_code == 200, response.text
    assert response.json() == {"items": [], "total": 0, "error": None}


def test_builds_newest_first_with_relative_paths_and_damaged_lines_ignored(
    user_client: TestClient,
    project: dict[str, object],  # noqa: F811
    migrated: Settings,
) -> None:
    history = _history(migrated)
    history.parent.mkdir(parents=True)
    moved = ContextChange(
        source_path=_source(migrated, "2024/enero/factura.pdf"),
        change="reclassified",
        previous_domain="informes",
        domain="facturas",
        classified_by="rules",
    )
    history.write_text(
        "\n".join(
            [
                _record("2026-11-01T08:00:00+00:00"),
                "{esto no es json",
                '{"built_at": "2026-11-03T08:00:00+00:00"}',  # le faltan campos obligatorios
                _record("2026-11-02T08:00:00+00:00", moved, classified=3),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    body = user_client.get(_url(project)).json()

    assert body["total"] == 2 and body["error"] is None
    newest, oldest = body["items"]
    assert newest["built_at"].startswith("2026-11-02") and oldest["built_at"].startswith("2026-11-01")
    assert (newest["classified"], newest["changes_total"], newest["ai_classification_model"]) == (3, 1, "clasificador")
    (change,) = newest["changes"]
    assert change | {"path": None} == {
        "path": None,
        "change": "reclassified",
        "previous_domain": "informes",
        "domain": "facturas",
        "previous_material_type": None,
        "material_type": None,
        "classified_by": "rules",
    }
    assert str(migrated.locations_root) not in str(body)
    limited = user_client.get(_url(project), params={"limit": 1}).json()
    assert limited["total"] == 2 and len(limited["items"]) == 1


@pytest.mark.posix_paths
def test_change_paths_are_relative_to_the_source_folder(
    user_client: TestClient,
    project: dict[str, object],  # noqa: F811
    migrated: Settings,
) -> None:
    history = _history(migrated)
    history.parent.mkdir(parents=True)
    added = ContextChange(source_path=_source(migrated, "2024/enero/factura.pdf"), change="added", domain="facturas")
    history.write_text(_record("2026-11-01T08:00:00+00:00", added) + "\n", encoding="utf-8")

    (build,) = user_client.get(_url(project)).json()["items"]

    assert [c["path"] for c in build["changes"]] == ["2024/enero/factura.pdf"]


def test_changes_are_capped_per_build(
    user_client: TestClient,
    project: dict[str, object],  # noqa: F811
    migrated: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.v1.context import documents as context_documents

    monkeypatch.setattr(context_documents, "MAX_HISTORY_CHANGES", 2)
    history = _history(migrated)
    history.parent.mkdir(parents=True)
    added = [ContextChange(source_path=_source(migrated, f"2024/{i}.pdf"), change="added") for i in range(5)]
    history.write_text(_record("2026-11-01T08:00:00+00:00", *added) + "\n", encoding="utf-8")

    (build,) = user_client.get(_url(project)).json()["items"]

    assert build["changes_total"] == 5 and len(build["changes"]) == 2


def test_too_large_asks_for_the_excel(
    user_client: TestClient,
    project: dict[str, object],  # noqa: F811
    migrated: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(context_service, "MAX_HISTORY_BYTES", 10)
    history = _history(migrated)
    history.parent.mkdir(parents=True)
    history.write_text(_record("2026-11-01T08:00:00+00:00") + "\n", encoding="utf-8")

    assert user_client.get(_url(project)).json() == {"items": [], "total": 0, "error": "history_too_large"}


@pytest.mark.skipif(sys.platform == "win32", reason="enlaces simbólicos sin privilegios solo en POSIX")
def test_a_linked_history_is_not_followed(
    user_client: TestClient,
    project: dict[str, object],  # noqa: F811
    migrated: Settings,
    tmp_path: Path,
) -> None:
    outside = tmp_path / "fuera.jsonl"
    outside.write_text(_record("2026-11-01T08:00:00+00:00") + "\n", encoding="utf-8")
    history = _history(migrated)
    history.parent.mkdir(parents=True)
    os.symlink(outside, history)

    assert user_client.get(_url(project)).json()["items"] == []


def test_history_is_for_members_only(client: TestClient, project: dict[str, object]) -> None:  # noqa: F811
    client.cookies.clear()
    assert client.get(_url(project)).status_code == 401
