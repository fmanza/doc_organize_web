"""Reglas puras de proyectos y ejecuciones (Fase 3): nombres de carpeta, solapes y catálogo de operaciones."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.projects.folders import folder_name_problem, nested, without_nested
from app.domain.runs.operations import (
    RUN_PARAMS,
    HistoryClearParams,
    NoopParams,
    ProjectDeleteParams,
    ProjectMoveParams,
    is_write,
    preview_matches,
    stored_params,
)


@pytest.mark.parametrize("name", ["Proyecto A", "expedientes-2024", "Año 2025 (copia)", "a.b"])
def test_valid_folder_names(name: str) -> None:
    assert folder_name_problem(name) is None


@pytest.mark.parametrize(
    "name",
    [
        "",
        "  ",
        " x",
        "x ",
        "a/b",
        "a\\b",
        "a:b",
        "a*b",
        'a"b',
        "a\x01",
        "CON",
        "nul.txt",
        "com1",
        "fin.",
        "..",
        "x" * 121,
    ],
)
def test_invalid_folder_names(name: str) -> None:
    assert folder_name_problem(name) is not None


def test_folder_name_requires_nfc() -> None:
    assert folder_name_problem("Anõ") is not None  # «Año» descompuesto


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        ("a", "a", True),
        ("a", "a/b", True),
        ("a/b", "a", True),
        ("", "x", True),
        ("a", "ab", False),
        ("a/b", "a/c", False),
    ],
)
def test_nested(a: str, b: str, expected: bool) -> None:
    assert nested(a, b) is expected


def test_without_nested_keeps_outermost() -> None:
    assert without_nested(["2024/enero", "2024", "2025", "2025"]) == ["2024", "2025"]
    assert without_nested(["b", "", "a"]) == [""]


def test_run_params_discriminated_by_operation() -> None:
    assert isinstance(RUN_PARAMS.validate_python({"operation": "noop"}), NoopParams)
    move = RUN_PARAMS.validate_python(
        {"operation": "project_move", "destination_location_id": 2, "new_folder": "Nuevo"}
    )
    assert isinstance(move, ProjectMoveParams) and move.dry_run is True
    with pytest.raises(ValidationError):
        RUN_PARAMS.validate_python({"operation": "scan"})
    with pytest.raises(ValidationError):
        RUN_PARAMS.validate_python({"operation": "noop", "secret": "x"})  # extra prohibido


def test_only_real_destructive_runs_write() -> None:
    assert not is_write(NoopParams())
    assert not is_write(HistoryClearParams())
    assert is_write(HistoryClearParams(dry_run=False))
    assert is_write(ProjectDeleteParams(dry_run=False, delete_outputs=True))


def test_preview_must_match_relevant_params() -> None:
    preview = stored_params(ProjectDeleteParams(delete_outputs=True))
    assert preview_matches(ProjectDeleteParams(dry_run=False, delete_outputs=True), preview)
    assert not preview_matches(ProjectDeleteParams(dry_run=False, delete_outputs=False), preview)
    assert not preview_matches(HistoryClearParams(dry_run=False), preview)
    real = stored_params(ProjectDeleteParams(dry_run=False, delete_outputs=True))
    assert not preview_matches(ProjectDeleteParams(dry_run=False, delete_outputs=True), real)  # no es vista previa
