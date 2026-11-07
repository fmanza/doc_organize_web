"""web 1.1.0: ``run_scan`` pasa los tramos, el timeout, los reintentos y los hashes a ``ScanOptions`` (doc_organize 1.1.0,
G38 y G11) y decide si hay otro tramo por ``ScanSummary.stopped_reason``, sin contar eventos."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import doc_organize
import pytest
from doc_organize import ScanEventType

from app.integrations.doc_organize import ScanRequest, run_scan


class _Event:
    def __init__(self, event: ScanEventType, data: dict[str, Any]) -> None:
        self.event, self.data, self.schema_version = event, data, 1


def _fake(monkeypatch: pytest.MonkeyPatch, final: ScanEventType, summary: dict[str, Any]) -> list[Any]:
    seen: list[Any] = []

    class FakeScanCommand:
        async def run_streaming(self, *args: Any, options: Any, **kwargs: Any) -> AsyncIterator[_Event]:
            seen.append(options)
            yield _Event(final, summary)

    monkeypatch.setattr(doc_organize, "ScanCommand", FakeScanCommand)
    return seen


def _request(tmp_path: Path, **kwargs: Any) -> ScanRequest:
    return ScanRequest(
        folders=[tmp_path / "origen"],
        output_root=tmp_path / "salidas",
        state_root=tmp_path / "estado",
        models_dir=tmp_path / "modelos",
        **kwargs,
    )


def test_options_reach_scan_options(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    seen = _fake(monkeypatch, ScanEventType.COMPLETED, {"converted": 3, "remaining": 0, "stopped_reason": None})
    request = _request(tmp_path, max_conversions=200, document_timeout_seconds=900, io_retries=2, reuse_hashes=True)

    outcome = run_scan(request, on_progress=lambda _: None, is_cancelled=lambda: False)

    (options,) = seen
    assert (options.max_documents, options.document_timeout_s) == (200, 900.0)
    assert (options.io_retries, options.reuse_unchanged_hashes) == (2, True)
    assert not outcome.recycled and outcome.summary["converted"] == 3


def test_zero_means_no_limit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    seen = _fake(monkeypatch, ScanEventType.COMPLETED, {})

    run_scan(_request(tmp_path), on_progress=lambda _: None, is_cancelled=lambda: False)

    (options,) = seen
    assert (options.max_documents, options.document_timeout_s, options.io_retries) == (None, None, 0)
    assert options.reuse_unchanged_hashes is False


def test_max_documents_with_pending_work_recycles(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _fake(monkeypatch, ScanEventType.COMPLETED, {"converted": 1, "remaining": 4, "stopped_reason": "max_documents"})

    outcome = run_scan(_request(tmp_path, max_conversions=1), on_progress=lambda _: None, is_cancelled=lambda: False)

    assert outcome.recycled and not outcome.cancelled


def test_cancelled_or_requested_stop_never_recycles(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _fake(monkeypatch, ScanEventType.CANCELLED, {"converted": 1, "stopped_reason": "max_documents"})
    outcome = run_scan(_request(tmp_path, max_conversions=1), on_progress=lambda _: None, is_cancelled=lambda: False)
    assert outcome.cancelled and not outcome.recycled

    _fake(monkeypatch, ScanEventType.COMPLETED, {"remaining": 2, "stopped_reason": "max_documents"})
    outcome = run_scan(_request(tmp_path, max_conversions=1), on_progress=lambda _: None, is_cancelled=lambda: True)
    assert not outcome.recycled  # el usuario pidió cancelar: el worker cierra el run, no lo relanza


def test_exclusions_reach_scan_options(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """web 1.4.0 (doc_organize 1.3.0, G41): subcarpetas absolutas y patrones de nombre."""
    seen = _fake(monkeypatch, ScanEventType.COMPLETED, {"excluded_cached": 2})
    excluded = tmp_path / "origen" / "fotos"
    request = _request(tmp_path, exclude_paths=[excluded], ignore_patterns=["~$*", "@eaDir"])

    outcome = run_scan(request, on_progress=lambda _: None, is_cancelled=lambda: False)

    (options,) = seen
    assert options.exclude_paths == [str(excluded)]
    assert options.ignore_patterns == ["~$*", "@eaDir"]
    assert outcome.summary["excluded_cached"] == 2


def test_without_exclusions_scan_options_keep_their_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    seen = _fake(monkeypatch, ScanEventType.COMPLETED, {})

    run_scan(_request(tmp_path), on_progress=lambda _: None, is_cancelled=lambda: False)

    (options,) = seen
    assert options.exclude_paths == [] and options.ignore_patterns == []
    assert "exclude_paths" not in options.model_fields_set and "ignore_patterns" not in options.model_fields_set
