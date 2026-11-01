"""Reglas puras de proyectos y ejecuciones (Fases 3 y 4): nombres de carpeta, solapes, catálogo de operaciones y
escaneo (rol, cola, vista previa, opciones contra capacidades y rutas sin el contenedor)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.projects.folders import folder_name_problem, nested, nested_pair
from app.domain.runs.operations import (
    RUN_PARAMS,
    HistoryClearParams,
    NoopParams,
    ProjectDeleteParams,
    ProjectMoveParams,
    ScanParams,
    is_write,
    min_role,
    needs_preview,
    preview_matches,
    queue_for,
    stored_params,
)
from app.domain.scan.options import missing_options
from app.jobs.operations.scan import PathMasker


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


def test_nested_pair_finds_folder_inside_another() -> None:
    assert nested_pair(["2024/enero", "2024", "2025", "2025"]) == ("2024", "2024/enero")
    assert nested_pair(["b", "", "a"]) == ("", "a")
    assert nested_pair(["a", "b", "a"]) is None


def test_run_params_discriminated_by_operation() -> None:
    assert isinstance(RUN_PARAMS.validate_python({"operation": "noop"}), NoopParams)
    move = RUN_PARAMS.validate_python(
        {"operation": "project_move", "destination_location_id": 2, "new_folder": "Nuevo"}
    )
    assert isinstance(move, ProjectMoveParams) and move.dry_run is True
    assert isinstance(RUN_PARAMS.validate_python({"operation": "scan"}), ScanParams)
    with pytest.raises(ValidationError):
        RUN_PARAMS.validate_python({"operation": "scan", "dry_run": True})  # vista previa solo con force
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


def test_scan_role_queue_and_preview() -> None:
    plain = ScanParams()
    assert is_write(plain) and not needs_preview(plain)
    assert min_role(plain) == "editor" and queue_for(plain) == "cpu"
    assert queue_for(ScanParams(use_gpu=True)) == "gpu"
    preview = ScanParams(force=True, dry_run=True)
    assert not is_write(preview) and not needs_preview(preview) and queue_for(preview) == "cpu"
    force = ScanParams(force=True)
    assert min_role(force) == "owner" and needs_preview(force)
    assert preview_matches(force, stored_params(preview))
    assert not preview_matches(force, stored_params(ScanParams(force=True, dry_run=False)))


def test_scan_options_need_a_capable_worker() -> None:
    params = ScanParams(use_gpu=True, include_audio_video=True, use_picture_description=True)
    assert missing_options(params, []) == ["use_gpu", "include_audio_video", "use_picture_description"]
    caps = [{"gpu_ready": False, "av_ready": True}, {"picture_description_ready": True}]
    assert missing_options(params, caps) == ["use_gpu"]
    assert missing_options(ScanParams(), []) == []


def test_path_masker_hides_container_paths() -> None:
    from pathlib import Path

    masker = PathMasker([(Path("/mnt/docs"), "«Origen»"), (Path("/mnt/docs/sub"), "«Sub»"), (Path("/data/p/1"), "«e»")])
    assert masker.relative("/mnt/docs/a/b.pdf") == "a/b.pdf"
    assert masker.relative("/mnt/docs/sub/c.pdf") == "c.pdf"  # la raíz más concreta
    assert masker.relative("/otra/ruta/x.pdf") == "x.pdf"
    assert masker.relative("/mnt/docsX/y.pdf") == "y.pdf"  # no es un prefijo de carpeta
    assert masker.text("Error en /mnt/docs/a.pdf con /data/p/1/cache.db") == "Error en «Origen»/a.pdf con «e»/cache.db"


def test_path_redactor_removes_container_paths() -> None:
    from app.core.redact import PathRedactor

    redactor = PathRedactor([("/mnt", "«ubicaciones»"), ("/data", "«datos»")])
    text = 'No se pudo listar "/mnt/docs/2024": [Errno 5] en /opt/venv/lib/x.py y /data/projects/1/cache.db'
    assert (
        redactor.text(text)
        == 'No se pudo listar "«ubicaciones»/docs/2024": [Errno 5] en «ruta» y «datos»/projects/1/cache.db'
    )
    assert redactor.text("/mntx/a y /tmp/b") == "/mntx/a y «ruta»"  # /mntx no es /mnt


def test_run_log_keeps_app_records_and_library_warnings_without_paths_or_traces() -> None:
    import json
    import logging

    from app.core.redact import PathRedactor, RedactingJsonFormatter, RunLogFilter

    log_filter = RunLogFilter()
    debug = logging.makeLogRecord({"name": "docling.models", "levelno": logging.INFO, "msg": "x"})
    assert not log_filter.filter(debug)
    try:
        raise OSError("/mnt/docs/secreto.pdf")
    except OSError:
        import sys

        record = logging.LogRecord(
            "doc_organize.scan", logging.ERROR, __file__, 1, "Falló %s", ("/mnt/docs/a.pdf",), sys.exc_info()
        )
    assert log_filter.filter(record)
    line = json.loads(RedactingJsonFormatter(PathRedactor([("/mnt", "«ubicaciones»")])).format(record))
    assert line["msg"] == "Falló «ubicaciones»/docs/a.pdf"
    assert line["exc_type"] == "OSError" and "exc" not in line
