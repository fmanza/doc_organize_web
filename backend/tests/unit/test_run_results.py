"""Resultados de las ejecuciones tipados (3.0, PR 3a): lo guardado no cambia y los históricos se siguen leyendo."""

from __future__ import annotations

import json
import logging
from typing import Any

import pytest

from app.domain.ai import usage_log
from app.domain.runs.operations import OPERATIONS
from app.domain.runs.results import (
    RESULT_MODELS,
    AiPhaseResult,
    ContextBuildResult,
    DedupApplyResult,
    DedupPreviewResult,
    ProjectDeleteResult,
    ScanResult,
    ScanResume,
    SemanticResult,
    TaxonomyDraftResult,
    parse_result,
    parse_result_as,
)


def _same_json(stored: dict[str, Any], legacy: dict[str, Any]) -> None:
    """Mismas claves, valores, tipos JSON (``0`` no pasa a ``0.0``) y orden que el diccionario de antes."""
    assert stored == legacy
    assert json.dumps(stored) == json.dumps(legacy)


# Resultados tal como los escribían las operaciones cuando devolvían diccionarios (2.8).
LEGACY: list[tuple[str, dict[str, Any]]] = [
    ("noop", {"steps": 3}),
    (
        "scan",
        {
            "folders": 2,
            "force": False,
            "scanned": 10,
            "new": 4,
            "modified": 1,
            "unchanged": 5,
            "converted": 5,
            "conversion_errors": 0,
            "ocr_required": 1,
            "ocr_processed": 1,
            "error_retries": 0,
            "error_retries_capped": 0,
            "io_errors": 0,
            "duration_seconds": 12.345,
            "discovery_duration_seconds": 0,
            "total_conversion_seconds": 10.5,
            "errors": 0,
            "warnings": 1,
            "event_schema_version": 1,
            "segments": 2,
            "search_indexed": 5,
        },
    ),
    ("scan", {"cached": 7, "orphaned": 1, "excluded": 2, "output_files": 14, "output_bytes": 2048}),
    (
        "project_delete",
        {
            "delete_outputs": False,
            "output_files": None,
            "output_bytes": None,
            "state_files": 3,
            "state_bytes": 10,
            "leftovers": 0,
        },
    ),
    (
        "dedup_preview",
        {
            "documents": 5,
            "groups": 1,
            "exact_groups": 1,
            "version_groups": 0,
            "fuzzy_groups": 0,
            "duplicate_files": 1,
            "reclaimable_bytes": 100,
            "stale_cache": 0,
            "excluded": 0,
            "fuzzy_threshold": None,
        },
    ),
    (
        "dedup_apply",
        {
            "mode": "copy",
            "groups": 2,
            "processed": 2,
            "failed": 0,
            "failed_paths": [],
            "groups_done": 2,
            "skipped_changed": 0,
        },
    ),
    (
        "context_build",
        {
            "output_folder_name": "organizado",
            "domains": 2,
            "documents": 3,
            "unclassified": 1,
            "failed": 0,
            "failed_paths": [],
            "missing_originals": 0,
            "site_built": False,
            "ai": {
                "enabled": True,
                "calls": 2,
                "failed": 0,
                "stopped": None,
                "cached": 0,
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "response_format": "json_schema",
                "classified": 2,
                "scope": "unclassified",
                "model": "m",
            },
            "ai_enrichment": {"enabled": False},
            "semantic": {"enabled": False},
        },
    ),
    (
        "taxonomy_draft",
        {
            "manifest_markdown": "---\n---\n",
            "reasoning": None,
            "sample_documents": 2,
            "total_documents": 4,
            "domains": [{"slug": "facturas", "name": "Facturas"}],
            "material_types": [],
            "model": "m",
            "prompt_tokens": 1,
            "completion_tokens": 2,
            "ai_cached": False,
        },
    ),
    (
        "export_ai_bundle",
        {
            "file_count": 3,
            "total_size_bytes": 30,
            "documents": 1,
            "superseded_skipped": 0,
            "missing_text": 0,
            "redacted_documents": 0,
            "full_text_truncated": False,
            "sha256": "0" * 64,
            "file_name": "p-ia.zip",
            "zip_size_bytes": 20,
            "include_text": True,
            "current_only": True,
            "redact": True,
            "max_file_chars": None,
            "max_full_chars": None,
        },
    ),
    (
        "context_review_agent",
        {
            "stop_reason": "finished",
            "finished": True,
            "steps": 3,
            "tool_calls": 2,
            "prompt_tokens": 10,
            "completion_tokens": 4,
            "tokens_estimated": False,
            "duration_s": 1.5,
            "model": "m",
            "max_steps": 40,
            "max_items": 20,
            "reviewed": 2,
            "summary": None,
            "proposals": 1,
        },
    ),
]


def test_every_operation_has_a_result_model() -> None:
    assert set(RESULT_MODELS) == set(OPERATIONS)


@pytest.mark.parametrize(("operation", "legacy"), LEGACY, ids=[f"{op}-{i}" for i, (op, _) in enumerate(LEGACY)])
def test_stored_result_is_identical_to_the_dict_written_before(operation: str, legacy: dict[str, Any]) -> None:
    parsed = parse_result(operation, legacy, run_id="r1")
    assert parsed is not None and isinstance(parsed, RESULT_MODELS[operation])
    _same_json(parsed.stored(), legacy)


def test_models_built_by_the_operations_store_only_what_they_write() -> None:
    # Vista previa sin borrar salidas: ``output_files`` va como ``None`` y ``leftovers`` no aparece.
    preview = ProjectDeleteResult(
        delete_outputs=False, output_files=None, output_bytes=None, state_files=1, state_bytes=2
    )
    _same_json(
        preview.stored(),
        {"delete_outputs": False, "output_files": None, "output_bytes": None, "state_files": 1, "state_bytes": 2},
    )
    preview.leftovers = 0  # lo que se asigna después también se guarda
    assert list(preview.stored())[-1] == "leftovers"

    dedup = DedupPreviewResult(documents=1, groups=0, fuzzy_threshold=None)
    assert dedup.stored() == {"documents": 1, "groups": 0, "fuzzy_threshold": None}  # sin claves de contenido

    real = DedupApplyResult(mode="move", groups=1)
    real.processed, real.failed, real.failed_paths, real.groups_done, real.skipped_changed = 1, 0, [], 1, 0
    assert list(real.stored()) == [
        "mode",
        "groups",
        "processed",
        "failed",
        "failed_paths",
        "groups_done",
        "skipped_changed",
    ]

    build = ContextBuildResult(
        ai=AiPhaseResult.model_validate({"enabled": False}),
        semantic=SemanticResult.model_validate({"enabled": False}),
    )
    assert build.stored() == {"ai": {"enabled": False}, "semantic": {"enabled": False}}


def test_a_scan_segment_keeps_the_internal_resume_state_last() -> None:
    segment = ScanResult.model_validate({"folders": 1, "force": False, "converted": 3})
    segment.resume = ScanResume(done=[], partial="2024", failed=[])
    _same_json(
        segment.stored(),
        {"folders": 1, "force": False, "converted": 3, "resume": {"done": [], "partial": "2024", "failed": []}},
    )


def test_historical_results_with_retired_keys_still_validate() -> None:
    """``collisions`` (G30, doc_organize 0.13) y otras claves retiradas se conservan gracias a ``extra="allow"``."""
    scan = {"folders": 1, "force": False, "converted": 2, "collisions": 1, "collisions_count": 1}
    parsed = parse_result_as(ScanResult, scan, run_id="r-old")
    assert parsed is not None and parsed.converted == 2
    assert parsed.model_extra == {"collisions": 1, "collisions_count": 1}
    assert parsed.stored() == scan

    build = {"output_folder_name": "organizado", "collision": True, "ai": {"enabled": True, "calls": 1, "old": "x"}}
    old = parse_result("context_build", build)
    assert isinstance(old, ContextBuildResult) and old.ai is not None and old.ai.calls == 1
    assert old.stored() == build


def test_an_invalid_result_returns_none_and_logs_without_values(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="app.domain.runs.results"):
        assert parse_result("scan", {"converted": "secreto-no-numerico"}, run_id="r-bad") is None
        assert parse_result("taxonomy_draft", {"domains": "no-es-lista"}, run_id="r-bad2") is None
        assert parse_result("scan", ["no", "es", "objeto"], run_id="r-list") is None
        assert parse_result("desconocida", {"x": 1}, run_id="r-unknown") is None
    assert [getattr(r, "run_id", None) for r in caplog.records] == ["r-bad", "r-bad2", "r-list", "r-unknown"]
    assert all("secreto" not in str(r.__dict__) for r in caplog.records)
    assert parse_result("scan", None) is None


def test_ai_usage_reads_the_typed_result() -> None:
    draft = TaxonomyDraftResult(manifest_markdown="---\n---\n", model="m", prompt_tokens=3, ai_cached=False)
    [row] = usage_log.rows_from_result("taxonomy_draft", draft)
    assert (row.task, row.calls, row.cached, row.prompt_tokens) == ("taxonomy_design", 1, 0, 3)
    # Un resultado guardado que no valida no registra consumo (ni rompe el cierre del run).
    assert usage_log.rows_from_result("context_build", {"ai": {"enabled": True, "calls": "dos"}}) == []
