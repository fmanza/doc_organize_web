"""Calidad de la clasificación (W5, doc_organize 2.0 G3): referencia en Excel (sintética), evaluación del contexto y
clasificación de prueba sin guardar, con y sin IA (LiteLLM falso)."""

from __future__ import annotations

import io
import json
import os
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import AuditEntry, Project, User
from app.integrations.doc_organize import ai as library_ai
from app.jobs.context import JobFailed
from app.jobs.operations import context as operation
from app.jobs.operations import quality
from tests.conftest import ADMIN_PASSWORD, login_as
from tests.fake_litellm import FakeLiteLLM, classify_answer
from tests.jobs.test_context_axes import AXES_TEMPLATE
from tests.jobs.test_context_operation import DOMAINS, _finish

KEY = "sk-quality-test-5t6y"


def _xlsx(
    rows: list[tuple[str, str]], *, sheet: str = "Referencia", header: tuple[str, str] = ("documento", "dominio_ok")
) -> bytes:
    workbook = Workbook()
    ws = workbook.active
    assert ws is not None
    ws.title = sheet
    ws.append(list(header))
    for row in rows:
        ws.append(list(row))
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


GOLD = _xlsx([("2025/receta.txt", "informes"), ("2024/factura.txt", "facturas"), ("2025/factura.txt", "facturas")])


@pytest.fixture(autouse=True)
def _ai_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for family in library_ai.FAMILIES:
        for field in family.fields:
            if field.env_var:
                monkeypatch.delenv(field.env_var, raising=False)
    monkeypatch.setenv("DOC_ORGANIZE_LITELLM_BASE_URL", "https://litellm.example.internal")
    monkeypatch.setenv("DOC_ORGANIZE_LITELLM_VIRTUAL_KEY", KEY)


def _upload(client: TestClient, project: Project, content: bytes, **params: Any) -> Any:
    return client.put(
        f"/api/v1/projects/{project.id}/context/quality/gold",
        params=params,
        content=content,
        headers={"Content-Type": "application/octet-stream"},
    )


def test_gold_upload_is_checked(
    project: Project, user_client: TestClient, make_user: Callable[..., User], db: Session
) -> None:
    saved = _upload(user_client, project, GOLD, filename="ref.xlsx", columns=["domains:dominio_ok"])

    assert saved.status_code == 200, saved.text
    assert saved.json()["labels"] == 3 and saved.json()["axes"] == ["domains"]
    assert user_client.get(f"/api/v1/projects/{project.id}/context/quality").json()["gold"]["filename"] == "ref.xlsx"
    assert _upload(user_client, project, b"no es un excel").json()["code"] == "gold_invalid"
    assert _upload(user_client, project, GOLD, sheet="Otra").status_code == 422
    assert _upload(user_client, project, GOLD, document_column="clave").status_code == 422
    empty = _xlsx([("2025/receta.txt", "")])
    assert _upload(user_client, project, empty).status_code == 422
    viewer = make_user("lectora")
    user_client.post(f"/api/v1/projects/{project.id}/members", json={"user_id": viewer.id, "role": "viewer"})
    assert _upload(login_as(user_client, "lectora"), project, GOLD).status_code == 403
    entry = db.scalars(select(AuditEntry).where(AuditEntry.action == "project.gold_upload")).one()
    assert entry.details == {"labels": 3, "axes": ["domains"]}
    assert user_client.delete(f"/api/v1/projects/{project.id}/context/quality/gold").status_code == 204
    assert user_client.get(f"/api/v1/projects/{project.id}/context/quality").json()["gold"] is None


@pytest.mark.parametrize("content", ["[]", "null", '"texto"'])
def test_quality_survives_a_decisions_file_that_is_not_an_object(
    project: Project, user_client: TestClient, migrated: Settings, content: str
) -> None:
    """Un ``decisions.json`` válido como JSON pero que no es un objeto no rompe la página: «sin decisiones»."""
    store = migrated.locations_root / "salidas" / "Proyecto A" / ".doc_organize" / "decisions.json"
    store.parent.mkdir(parents=True, exist_ok=True)
    store.write_text(content, encoding="utf-8")

    response = user_client.get(f"/api/v1/projects/{project.id}/context/quality")

    assert response.status_code == 200, response.text
    assert response.json()["decisions_available"] is False


def test_quality_survives_an_unreadable_decisions_folder(
    project: Project, user_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sin permiso para ver ``.doc_organize`` (montaje de red), «sin decisiones» en lugar de un 500."""
    real_lstat = os.lstat

    def lstat(path: Any, *args: Any, **kwargs: Any) -> os.stat_result:
        if ".doc_organize" in str(path):
            raise PermissionError(13, "Permission denied", str(path))
        return real_lstat(path, *args, **kwargs)

    monkeypatch.setattr(os, "lstat", lstat)

    response = user_client.get(f"/api/v1/projects/{project.id}/context/quality")

    assert response.status_code == 200, response.text
    assert response.json()["decisions_available"] is False


def test_evaluate_the_context_against_the_excel(
    run: Any, project: Project, db: Session, user_client: TestClient
) -> None:
    ctx, params = run(DOMAINS)
    operation.run_build(ctx, params, project)
    _finish(db, ctx)
    _upload(user_client, project, GOLD)

    ctx2, params2 = run({"operation": "context_evaluate", "gold": "xlsx"})
    result = quality.run_evaluate(ctx2, params2, project)

    report = result["report"]
    assert report["matched"] == 3 and report["missing_total"] == 0
    domains = report["axes"]["domains"]
    assert domains["labelled"] == 3 and 0 <= domains["accuracy"] <= 1
    assert set(domains["labelled_by_classified_by"]) <= {"rules", "ai", "unclassified", "human"}
    assert json.dumps(result)  # serializable para runs.result


def test_evaluation_needs_a_reference(run: Any, project: Project, db: Session, user_client: TestClient) -> None:
    ctx, params = run(DOMAINS)
    operation.run_build(ctx, params, project)
    _finish(db, ctx)
    runs = f"/api/v1/projects/{project.id}/runs"

    without = user_client.post(runs, json={"operation": "context_evaluate", "gold": "xlsx"})
    ctx2, params2 = run({"operation": "context_evaluate", "gold": "decisions"})

    assert without.status_code == 422 and without.json()["code"] == "gold_not_found"
    with pytest.raises(JobFailed) as failure:  # sin decisiones, la referencia está vacía
        quality.run_evaluate(ctx2, params2, project)
    assert failure.value.code == "gold_invalid"


def test_dry_run_compares_without_saving(
    run: Any,
    project: Project,
    db: Session,
    user_client: TestClient,
    admin: User,
    migrated: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin_client = login_as(user_client, admin.username, ADMIN_PASSWORD)
    assert admin_client.put("/api/v1/taxonomy-templates/ejes", json={"markdown": AXES_TEMPLATE}).status_code == 201
    ctx, params = run(DOMAINS)
    operation.run_build(ctx, params, project)
    _finish(db, ctx)
    _upload(user_client, project, GOLD)
    context_file = migrated.locations_root / "salidas" / "Proyecto A" / "context.json"
    before = context_file.read_bytes()
    proxy = FakeLiteLLM(keys={KEY}).install(monkeypatch)
    proxy.answers["classify"] = classify_answer({"domains": ["informes"], "material_types": ["original"]})

    ctx2, params2 = run(
        {
            "operation": "context_dry_run",
            "gold": "xlsx",
            "catalog": "template",
            "template_name": "ejes",
            "ai_scope": "unclassified",
            "model_classify": "modelo-candidato",
            "profile_markdown": "## Glosario\n- Receta: documento de cocina sintético.\n",
            "max_documents": 1,
        }
    )
    result = quality.run_dry_run(ctx2, params2, project)

    assert result["baseline"]["axes"]["domains"]["labelled"] == 3
    assert result["candidate"]["axes"]["domains"]["labelled"] == 3 and result["documents"] == 3
    assert result["ai"]["calls"] <= 1 and result["ai"]["model"] == "modelo-candidato"
    assert result["changes_total"] == len(result["changes"]) >= 1  # rc2: cambios frente al contexto actual
    assert {"document_key", "axis", "before", "after"} <= set(result["changes"][0])
    sent = proxy.sent("classify")
    assert all(r.body["model"] == "modelo-candidato" for r in sent)
    assert "documento de cocina sintético" in proxy.text_sent()  # el perfil candidato llega al prompt
    assert context_file.read_bytes() == before  # no guarda nada
    stored = db.scalars(select(AuditEntry).where(AuditEntry.action == "project.dry_run")).one()
    assert stored.details["calls"] == result["ai"]["calls"]  # type: ignore[index]
    public = user_client.get(f"/api/v1/runs/{ctx2.run_id}").json()["params"]
    assert "profile_markdown" not in public and "template_markdown" not in public
