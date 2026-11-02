"""Piezas puras de la Fase 5: rutas de salida (G20), nombres de documentos sin rutas del contenedor, consulta FTS5
segura, constantes contra ``ProjectLayout`` y copia de seguridad de las bases de datos."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from doc_organize import ProjectLayout

from app.core.config import Settings
from app.db import backup
from app.domain.documents.outputs import output_paths
from app.domain.documents.paths import DocumentNamer
from app.domain.scan.state import CACHE_DB, CONVERSION_DIR, folder_cache
from app.domain.search.index import match_query


@pytest.mark.parametrize(
    ("folder", "relative", "markdown", "images"),
    [
        ("2024", "factura.pdf", "2024/factura.md", "2024/img/factura"),
        ("2024", "facturas /enero. .pdf", "2024/facturas/enero.md", "2024/facturas/img/enero"),
        ("", "a/b/c.docx", "a/b/c.md", "a/b/img/c"),
        ("2024/enero", "x.tar.gz", "2024/enero/x.tar.md", "2024/enero/img/x.tar"),
    ],
)
def test_output_paths_follow_doc_organize(folder: str, relative: str, markdown: str, images: str) -> None:
    paths = output_paths(folder, relative)

    assert (paths.markdown, paths.images) == (markdown, images)
    assert paths.json == markdown[:-3] + ".json"


def test_state_names_match_project_layout(tmp_path: Path) -> None:
    layout = ProjectLayout(tmp_path / "salidas", state_root=tmp_path / "estado")

    assert layout.conversion_dir == tmp_path / "salidas" / CONVERSION_DIR
    assert layout.cache_db == tmp_path / "estado" / CACHE_DB
    assert folder_cache(tmp_path, "2024").name == CACHE_DB


def test_document_namer_keeps_paths_relative_to_their_folder() -> None:
    namer = DocumentNamer(
        [("2024", [Path("/mnt/docs/2024"), Path("/mnt/real/2024")]), ("2024/enero", [Path("/mnt/docs/2024/enero")])],
        "Origen",
    )

    assert namer.split("/mnt/docs/2024/enero/a.pdf") == ("2024/enero", "a.pdf")
    assert namer.display("/mnt/real/2024/b/c.pdf") == "2024/b/c.pdf"
    assert namer.display("/otra/parte/d.pdf") == "d.pdf"
    assert namer.split("/mnt/docs/20245/x.pdf") is None
    assert namer.text("Error en /mnt/docs/2024/a.pdf y /opt/venv/x.py") == "Error en «Origen»/2024/a.pdf y «ruta»"


@pytest.mark.parametrize(
    ("text", "query"),
    [
        ("luz", '"luz"*'),
        ("factura  enero", '"factura"* "enero"*'),
        ('luz OR "x NEAR( title:*', '"luz"* "OR"* "NEAR"* "title"*'),
        ("a y b", None),
        ("¿?", None),
        (" ".join(f"palabra{n}" for n in range(12)), " ".join(f'"palabra{n}"*' for n in range(8))),
    ],
)
def test_match_query_never_passes_fts_syntax(text: str, query: str | None) -> None:
    assert match_query(text) == query


def test_backup_copies_config_and_caches_and_verifies(migrated: Settings, tmp_path: Path) -> None:
    cache = migrated.data_dir / "projects" / "1" / "folders" / "abc" / "cache.db"
    cache.parent.mkdir(parents=True)
    with sqlite3.connect(cache) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE t (x)")
        conn.execute("INSERT INTO t VALUES (1)")
    (migrated.data_dir / "projects" / "1" / "search.db").write_bytes(b"")

    first = backup.create_backup(migrated, destination=tmp_path / "copias")
    copied = sorted(str(p.relative_to(first).as_posix()) for p in first.rglob("*.db"))

    assert copied == ["config.db", "projects/1/folders/abc/cache.db"]
    assert backup.verify_backup(first) == []
    assert not [p for p in first.rglob("*") if p.name.endswith(("-wal", "-shm"))]
    (first / "projects/1/folders/abc/cache.db").write_bytes(b"roto")
    assert backup.verify_backup(first) == [
        "projects/1/folders/abc/cache.db: el contenido no coincide con el manifiesto."
    ]


def test_backup_keeps_the_newest(migrated: Settings, tmp_path: Path) -> None:
    root = tmp_path / "copias"
    for stamp in ("20260101T000000Z", "20260102T000000Z"):
        (root / stamp).mkdir(parents=True)
        (root / stamp / backup.MANIFEST).write_text('{"files": []}', encoding="utf-8")

    newest = backup.create_backup(migrated, destination=root, keep=2)

    assert [p.name for p in backup.backups(root)] == ["20260102T000000Z", newest.name]
