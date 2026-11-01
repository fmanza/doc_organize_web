"""Manifiesto de modelos (ADR-011): estado y mezcla de grupos entre descargas de models-init y models-init-gpu."""

from __future__ import annotations

import json
from pathlib import Path

from app.integrations.doc_organize.models import MANIFEST, docling_dir, merge_folders, status


def _write_manifest(root: Path, folders: dict[str, list[str]]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for names in folders.values():
        for name in names:
            (root / name).mkdir(exist_ok=True)
    (root / MANIFEST).write_text(json.dumps({"folders": folders}), encoding="utf-8")


def test_merge_keeps_optional_groups_downloaded_before(tmp_path: Path) -> None:
    root = docling_dir(tmp_path)
    _write_manifest(root, {"base": ["layout"], "picture_description": [], "easyocr": ["EasyOcr"]})

    merged = merge_folders(root, {"base": ["layout"], "picture_description": ["smolvlm"], "easyocr": []})

    assert merged == {"base": ["layout"], "picture_description": ["smolvlm"], "easyocr": ["EasyOcr"]}


def test_merge_drops_groups_whose_folders_are_gone(tmp_path: Path) -> None:
    root = docling_dir(tmp_path)
    _write_manifest(root, {"base": ["layout"], "picture_description": [], "easyocr": ["EasyOcr"]})
    (root / "EasyOcr").rmdir()

    merged = merge_folders(root, {"base": ["layout"], "picture_description": [], "easyocr": []})

    assert merged["easyocr"] == []


def test_merge_without_previous_or_invalid_manifest(tmp_path: Path) -> None:
    root = docling_dir(tmp_path)
    downloaded = {"base": ["layout"], "picture_description": [], "easyocr": []}
    assert merge_folders(root, downloaded) == downloaded

    root.mkdir(parents=True)
    (root / MANIFEST).write_text("[]", encoding="utf-8")
    assert merge_folders(root, downloaded) == downloaded


def test_status_reads_manifest_and_folders(tmp_path: Path) -> None:
    assert not status(tmp_path).ready
    _write_manifest(docling_dir(tmp_path), {"base": ["layout"], "picture_description": [], "easyocr": ["EasyOcr"]})

    result = status(tmp_path)

    assert result.ready
    assert result.easyocr
    assert not result.picture_description
