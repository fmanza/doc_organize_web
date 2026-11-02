"""Búsqueda de texto completo sobre el Markdown convertido (mejora opcional de la Fase 5, SQLite FTS5).

Un índice por proyecto en ``/data/projects/<id>/search.db`` (volumen local, nunca en red; ADR-005). Lo escribe solo el
worker (``reindex``, al terminar un escaneo o con el run ``search_index``) y la API lo abre en solo lectura
(``search``). No es una tabla de ``config.db``: con 100 000 documentos ocupa gigas y se regenera desde las salidas, así
que va fuera de Alembic; si cambia ``SCHEMA_VERSION``, se reconstruye entero.

El índice es incremental: cada ``.md`` de ``Conversión/`` se reindexa si cambia su ``mtime`` o su tamaño, y se borra
del índice si ya no está.
"""

from __future__ import annotations

import os
import re
import sqlite3
import time
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from app.domain.search.errors import SearchTooBroadError

SEARCH_DB: Final = "search.db"
SCHEMA_VERSION: Final = 1
#: Texto que se indexa por documento: acota el índice ante un Markdown de cientos de MB.
MAX_INDEXED_CHARS: Final = 2_000_000
BATCH: Final = 200
#: Marcas de las coincidencias en el fragmento: el cliente las pinta como texto, nunca como HTML.
MARK_START: Final = "\u0002"
MARK_END: Final = "\u0003"
_TOKEN: Final = re.compile(r"[\w]+", re.UNICODE)
#: Palabras por consulta y longitud mínima de cada una (una letra sola casa con casi todo el índice).
MAX_TOKENS: Final = 8
MIN_TOKEN: Final = 2
#: Tiempo máximo de una consulta en la API antes de pedir que se concrete.
QUERY_SECONDS: Final = 5.0
_SCHEMA: Final = (
    "CREATE VIRTUAL TABLE IF NOT EXISTS docs USING fts5(path UNINDEXED, title, body, "
    "tokenize='unicode61 remove_diacritics 2')",
    "CREATE TABLE IF NOT EXISTS files (path TEXT PRIMARY KEY, mtime_ns INTEGER NOT NULL, size INTEGER NOT NULL, "
    "doc_id INTEGER NOT NULL)",
    "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
)


@dataclass(frozen=True)
class IndexStats:
    """Resultado de un reindexado: documentos añadidos, actualizados, quitados y total en el índice."""

    added: int = 0
    updated: int = 0
    removed: int = 0
    total: int = 0


@dataclass(frozen=True)
class SearchHit:
    """Documento que coincide: Markdown relativo a ``Conversión/``, título y fragmento con las coincidencias marcadas."""

    output_path: str
    title: str
    snippet: str


def search_db(project_state: Path) -> Path:
    """Índice del proyecto dentro de su carpeta de estado."""
    return project_state / SEARCH_DB


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version not in (0, SCHEMA_VERSION):
        conn.executescript("DROP TABLE IF EXISTS docs; DROP TABLE IF EXISTS files; DROP TABLE IF EXISTS meta;")
    for statement in _SCHEMA:
        conn.execute(statement)
    conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
    conn.commit()
    return conn


def _title(text: str, fallback: str) -> str:
    for line in text.splitlines()[:200]:
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()[:300] or fallback
    return fallback


def _markdown_files(root: Path) -> dict[str, os.stat_result]:
    """``.md`` bajo ``root`` (relativos, con ``/``), sin seguir enlaces."""
    found: dict[str, os.stat_result] = {}
    for current, _dirnames, filenames in os.walk(root, followlinks=False):
        for name in filenames:
            if not name.lower().endswith(".md"):
                continue
            path = Path(current) / name
            try:
                stat = path.lstat()
            except OSError:
                continue
            if not path.is_symlink():
                found[path.relative_to(root).as_posix()] = stat
    return found


def reindex(
    index: Path,
    conversion_dir: Path,
    *,
    check_cancelled: Callable[[], None] = lambda: None,
    on_progress: Callable[[int, int], None] = lambda done, total: None,
) -> IndexStats:
    """Pone el índice al día con los ``.md`` de ``conversion_dir`` (incremental por ``mtime`` y tamaño).

    Args:
        index: ``search.db`` del proyecto.
        conversion_dir: Carpeta ``Conversión/`` del proyecto (si no existe, el índice queda vacío).
        check_cancelled: Punto seguro de parada (lanza para cancelar); lo indexado hasta ahí queda guardado.
        on_progress: ``(hechos, total)`` de los ficheros revisados.
    """
    files = _markdown_files(conversion_dir) if conversion_dir.is_dir() else {}
    added = updated = removed = 0
    with closing(_connect(index)) as conn:
        known = {
            row[0]: (row[1], row[2], row[3]) for row in conn.execute("SELECT path, mtime_ns, size, doc_id FROM files")
        }
        for gone in known.keys() - files.keys():
            conn.execute("DELETE FROM docs WHERE rowid = ?", (known[gone][2],))
            conn.execute("DELETE FROM files WHERE path = ?", (gone,))
            removed += 1
        conn.commit()
        for done, (rel, stat) in enumerate(sorted(files.items()), start=1):
            previous = known.get(rel)
            if previous is None or previous[:2] != (stat.st_mtime_ns, stat.st_size):
                try:
                    with (conversion_dir / rel).open(encoding="utf-8", errors="replace") as handle:
                        text = handle.read(MAX_INDEXED_CHARS)
                except OSError:
                    continue
                if previous is not None:
                    conn.execute("DELETE FROM docs WHERE rowid = ?", (previous[2],))
                cursor = conn.execute(
                    "INSERT INTO docs (path, title, body) VALUES (?, ?, ?)", (rel, _title(text, Path(rel).stem), text)
                )
                conn.execute(
                    "INSERT OR REPLACE INTO files (path, mtime_ns, size, doc_id) VALUES (?, ?, ?, ?)",
                    (rel, stat.st_mtime_ns, stat.st_size, cursor.lastrowid),
                )
                if previous is None:
                    added += 1
                else:
                    updated += 1
            if done % BATCH == 0:
                conn.commit()
                on_progress(done, len(files))
                check_cancelled()
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('indexed_at', ?)", (datetime.now(UTC).isoformat(),)
        )
        conn.commit()
        on_progress(len(files), len(files))
    return IndexStats(added=added, updated=updated, removed=removed, total=len(files))


def match_query(text: str) -> str | None:
    """Consulta FTS5 segura a partir de lo que escribe el usuario: cada palabra entre comillas y con prefijo (``*``),
    todas obligatorias. Nada de la sintaxis FTS5 (``OR``, ``NEAR``, ``column:``) llega tal cual."""
    tokens = [token for token in _TOKEN.findall(text) if len(token) >= MIN_TOKEN][:MAX_TOKENS]
    return " ".join(f'"{token}"*' for token in tokens) or None


def _like_prefix(folder: str) -> str:
    return folder.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "/%"


def search(
    index: Path, text: str, *, folders: list[str] | None = None, limit: int, offset: int
) -> tuple[list[SearchHit], int, datetime | None]:
    """Documentos que contienen todas las palabras de ``text``, los más relevantes primero.

    Args:
        folders: Solo salidas de estas carpetas de origen (``""`` = la raíz, sin filtro); ``None`` = todas.

    Returns:
        Página de coincidencias, total y cuándo se actualizó el índice (``None`` si aún no existe).

    Raises:
        SearchTooBroadError: La consulta pasa de ``QUERY_SECONDS``.
    """
    query = match_query(text)
    if not index.is_file():
        return [], 0, None
    deadline = time.monotonic() + QUERY_SECONDS
    with closing(sqlite3.connect(f"file:{index.as_posix()}?mode=ro", uri=True, timeout=10)) as conn:
        try:
            row = conn.execute("SELECT value FROM meta WHERE key = 'indexed_at'").fetchone()
        except sqlite3.OperationalError:  # el worker lo está creando o cambiando de esquema
            return [], 0, None
        indexed_at = datetime.fromisoformat(row[0]) if row else None
        if query is None or indexed_at is None:
            return [], 0, indexed_at
        where, params = "docs MATCH ?", [query]
        if folders is not None and "" not in folders:
            if not folders:
                return [], 0, indexed_at
            where += " AND (" + " OR ".join("path LIKE ? ESCAPE '\\'" for _ in folders) + ")"
            params.extend(_like_prefix(folder) for folder in folders)
        conn.set_progress_handler(lambda: int(time.monotonic() > deadline), 10_000)
        try:
            total = conn.execute(f"SELECT count(*) FROM docs WHERE {where}", params).fetchone()[0]  # noqa: S608 - fijo
            rows = conn.execute(
                f"SELECT path, title, snippet(docs, 2, ?, ?, '…', 16) FROM docs WHERE {where} "  # noqa: S608 - fijo
                "ORDER BY rank LIMIT ? OFFSET ?",
                [MARK_START, MARK_END, *params, limit, offset],
            ).fetchall()
        except sqlite3.OperationalError as exc:
            if "interrupted" in str(exc):
                raise SearchTooBroadError("Concreta más la búsqueda: añade palabras menos comunes.") from None
            raise
    return [SearchHit(output_path=r[0], title=r[1], snippet=r[2]) for r in rows], int(total), indexed_at
