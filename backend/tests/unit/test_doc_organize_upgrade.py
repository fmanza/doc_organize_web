"""Paso a doc_organize 1.5.0 (web 1.4.8): lo que cambia solo con el pin, contra la librería real (sin Docling)."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.integrations.doc_organize import cache, context


def _cache_1_4(path: Path, root: Path) -> None:
    """``cache.db`` escrita por doc_organize 1.1.0-1.4.0: sin las columnas de metadatos de fichero de 1.5.0."""
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE cache_entries (file_path TEXT PRIMARY KEY, sha256_hash TEXT NOT NULL, timestamp REAL NOT NULL, "
            "status TEXT NOT NULL, conversion_status TEXT, error_message TEXT, error_retry_count INTEGER NOT NULL "
            "DEFAULT 0, size_bytes INTEGER)"
        )
        conn.execute(
            "INSERT INTO cache_entries VALUES (?, ?, 1.0, 'new', 'success', NULL, 0, 7)",
            (str(root / "a.pdf"), "ab" * 32),
        )
    conn.close()


def test_the_api_reads_a_cache_written_by_doc_organize_1_4(tmp_path: Path) -> None:
    """La API abre la caché en solo lectura: hasta que el worker la migre, las columnas nuevas no existen."""
    root = tmp_path / "origen"
    cache_db = tmp_path / "cache.db"
    _cache_1_4(cache_db, root)

    (document,) = cache.documents_page(cache_db, root=root, limit=10, offset=0)

    assert document.path == str(root / "a.pdf")
    assert cache.count_documents(cache_db, root=root) == 1


def test_the_context_history_folder_cannot_be_the_reorganized_folder() -> None:
    assert context.check_folder_name("historial_contexto") is not None
    assert context.check_folder_name("organizado") is None


@pytest.mark.parametrize("content", [b"[]", b"\xff\xfe no es UTF-8", b'{"domains": ["no es un objeto"]}'])
def test_a_damaged_context_counts_as_no_context(tmp_path: Path, content: bytes) -> None:
    """Desde doc_organize 1.5.0 todo daño de ``context.json`` es ``ContextError``; antes ``[]`` era un ``TypeError``."""
    (tmp_path / "context.json").write_bytes(content)

    assert context.existing_folder_name(tmp_path, name="P", created_at=datetime.now(UTC)) is None
