"""Resultados y parámetros con forma histórica servidos por la API (3.0, PR 3b; condición 4 del AUDIT_PLAN).

``RunOut`` es una unión discriminada por ``operation`` con ``params`` y ``result`` tipados. Las ejecuciones guardadas
por versiones anteriores pueden tener claves que el modelo ya no declara, campos ausentes o, por un fallo, una forma
que no valida: lo válido se sirve tipado y tal como se guardó (solo las claves escritas); lo que no valida, como
``result: null`` con un aviso en el log, nunca un 500.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Location, Run, utcnow
from tests.conftest import project_payload

#: Resultados de operaciones como los guardaron versiones anteriores (sintéticos).
HISTORICAL: list[tuple[str, dict[str, Any], dict[str, Any]]] = [
    # Escaneo de la 1.x: sin los recuentos de la 2.x, con una clave retirada y el estado interno de los tramos.
    (
        "scan",
        {"operation": "scan", "folders": [], "use_ocr": True, "legacy_option": 1},
        {"scanned": 4, "converted": 3, "collisions": 2, "resume": {"done": ["2024"], "partial": None}},
    ),
    # Construcción del contexto con doc_organize 0.13: ``collisions`` y una fase de IA con una clave desconocida.
    (
        "context_build",
        {"operation": "context_build", "catalog": "discover"},
        {
            "output_folder_name": "Contexto",
            "domains": 2,
            "collisions": 1,
            "ai": {"enabled": True, "calls": 3, "retries": 1},
        },
    ),
    # Borrado del proyecto sin salidas: claves guardadas con ``None`` que la API tiene que devolver.
    (
        "project_delete",
        {"operation": "project_delete", "dry_run": False, "delete_outputs": False},
        {"delete_outputs": False, "output_files": None, "output_bytes": None, "state_files": 2},
    ),
    # Evaluación de la 2.x sin informe (falló antes de evaluar).
    ("context_evaluate", {"operation": "context_evaluate", "gold": "decisions"}, {"gold": "decisions"}),
]

#: Evaluación con un informe de doc_organize sin algunos campos y con una clave que la web no declara.
EVALUATION: dict[str, Any] = {
    "gold": "decisions",
    "report": {
        "axes": {"domains": {"axis": "domains", "labelled": 2, "accuracy": 0.5, "future_metric": 7}},
        "documents": 3,
        "matched": 2,
        "missing_documents": [],
    },
}
#: Lo que sirve la API: los informes de doc_organize van enteros, con sus valores por defecto en lo que falta.
EVALUATION_SERVED: dict[str, Any] = {
    "gold": "decisions",
    "report": {
        "axes": {
            "domains": {
                "axis": "domains",
                "multiple": False,
                "labelled": 2,
                "accuracy": 0.5,
                "coverage": None,
                "precision": None,
                "recall": None,
                "accuracy_by_classified_by": {},
                "labelled_by_classified_by": {},
                "confusions": [],
                "future_metric": 7,
            }
        },
        "documents": 3,
        "matched": 2,
        "missing_documents": [],
        "missing_total": None,
    },
}


@pytest.fixture
def project_id(user_client: TestClient, project_locations: dict[str, Location]) -> int:
    response = user_client.post("/api/v1/projects", json=project_payload(project_locations))
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


def _run(db: Session, project_id: int, operation: str, params: dict[str, Any], result: object) -> str:
    """Un run terminado escrito directamente en la BD, como lo dejó una versión anterior."""
    run_id = str(uuid.uuid4())
    db.add(
        Run(
            id=run_id,
            project_id=project_id,
            operation=operation,
            queue="cpu",
            status="succeeded",
            is_write=False,
            params=params,
            result=result,
            finished_at=utcnow(),
        )
    )
    db.commit()
    return run_id


@pytest.mark.parametrize(("operation", "params", "result"), HISTORICAL, ids=[row[0] for row in HISTORICAL])
def test_historical_results_are_served_typed_and_as_stored(
    user_client: TestClient,
    db: Session,
    project_id: int,
    operation: str,
    params: dict[str, Any],
    result: dict[str, Any],
) -> None:
    run_id = _run(db, project_id, operation, params, result)

    response = user_client.get(f"/api/v1/runs/{run_id}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["operation"] == operation
    # Las claves escritas (también las desconocidas y las guardadas con ``None``), sin ``resume`` ni campos en null.
    assert body["result"] == {key: value for key, value in result.items() if key != "resume"}
    assert body["params"]["operation"] == operation
    assert {key: body["params"][key] for key in params} == params


def test_doc_organize_reports_are_served_whole(user_client: TestClient, db: Session, project_id: int) -> None:
    run_id = _run(db, project_id, "context_evaluate", {"operation": "context_evaluate"}, EVALUATION)

    response = user_client.get(f"/api/v1/runs/{run_id}")

    assert response.status_code == 200, response.text
    assert response.json()["result"] == EVALUATION_SERVED


@pytest.mark.parametrize(
    ("operation", "result"),
    [
        ("scan", {"scanned": "muchos"}),
        ("context_build", {"ai": "sin IA"}),
        ("context_evaluate", {"report": {"axes": ["domains"]}}),
        ("scan", ["no", "es", "un", "objeto"]),
    ],
    ids=["wrong-type", "wrong-nested", "wrong-report", "not-an-object"],
)
def test_an_invalid_result_is_served_as_null_and_logged(
    user_client: TestClient,
    db: Session,
    project_id: int,
    caplog: pytest.LogCaptureFixture,
    operation: str,
    result: object,
) -> None:
    run_id = _run(db, project_id, operation, {"operation": operation}, result)

    with caplog.at_level(logging.WARNING, logger="app.domain.runs.results"):
        response = user_client.get(f"/api/v1/runs/{run_id}")

    assert response.status_code == 200, response.text
    assert response.json()["result"] is None
    warnings = [record for record in caplog.records if record.name == "app.domain.runs.results"]
    assert [getattr(record, "run_id", None) for record in warnings] == [run_id]


# Los parámetros que no validan se sirven sin validar: Pydantic avisa al serializar el valor con otro tipo.
@pytest.mark.filterwarnings("ignore:Pydantic serializer warnings:UserWarning")
def test_invalid_params_are_served_as_stored(
    user_client: TestClient, db: Session, project_id: int, caplog: pytest.LogCaptureFixture
) -> None:
    """Unos parámetros que ya no validan (un campo obligatorio ausente, otro con otro tipo) no dan un 500."""
    params = {"operation": "dedup_apply", "mode": "copy", "groups": [], "dry_run": "sí"}
    run_id = _run(db, project_id, "dedup_apply", params, {"mode": "copy", "files": 0})

    with caplog.at_level(logging.WARNING, logger="app.api.v1.runs"):
        response = user_client.get(f"/api/v1/runs/{run_id}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["params"]["dry_run"] == "sí"
    assert body["params"]["groups"] == 0  # la lista se resume en su número, como siempre
    assert body["result"] == {"mode": "copy", "files": 0}
    assert any(getattr(record, "run_id", None) == run_id for record in caplog.records)


def test_the_history_mixes_valid_and_invalid_results(user_client: TestClient, db: Session, project_id: int) -> None:
    valid = _run(db, project_id, "export_zip", {"operation": "export_zip"}, {"file_count": 2, "old_key": "x"})
    invalid = _run(db, project_id, "export_zip", {"operation": "export_zip"}, {"file_count": "dos"})

    response = user_client.get("/api/v1/runs", params={"project_id": project_id})

    assert response.status_code == 200, response.text
    results = {item["id"]: item["result"] for item in response.json()["items"]}
    assert results == {valid: {"file_count": 2, "old_key": "x"}, invalid: None}


def test_hidden_params_are_not_served(user_client: TestClient, db: Session, project_id: int) -> None:
    params = {"operation": "context_dry_run", "template_markdown": "# Plantilla", "profile_markdown": "# Perfil"}
    run_id = _run(db, project_id, "context_dry_run", params, None)

    body = user_client.get(f"/api/v1/runs/{run_id}").json()

    assert body["result"] is None
    assert "template_markdown" not in body["params"]
    assert "profile_markdown" not in body["params"]


def test_quality_serves_typed_results_and_skips_invalid_ones(
    user_client: TestClient, db: Session, project_id: int
) -> None:
    evaluate_id = _run(db, project_id, "context_evaluate", {"operation": "context_evaluate"}, EVALUATION)
    _run(db, project_id, "context_audit", {"operation": "context_audit"}, {"audit": {"axes": "todos"}})
    audit = {"audit": {"documents": 2, "findings": [{"kind": "empty_entry", "message": "Sin documentos"}]}}
    _run(db, project_id, "context_dry_run", {"operation": "context_dry_run"}, audit | {"changes": [{"axis": 1}]})

    response = user_client.get(f"/api/v1/projects/{project_id}/context/quality")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["evaluation"]["run_id"] == evaluate_id
    assert body["evaluation"]["result"] == EVALUATION_SERVED
    assert body["audit"] is None  # el único informe del auditor no valida
    assert body["dry_run"] is None  # ``changes`` con un eje que no es texto
