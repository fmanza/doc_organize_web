"""Copia de seguridad de ``config.db`` y de las cachés de doc_organize (mejora opcional de la Fase 5).

Usa la API de backup de SQLite (``sqlite3.Connection.backup``), que copia una base de datos en uso de forma coherente
(WAL incluido) sin parar la aplicación. Cada copia es una carpeta ``<destino>/<UTC>/`` con las bases de datos en las
mismas rutas relativas que en ``/data`` y un ``manifest.json`` con tamaño y SHA-256. ``search.db`` no se copia: se
regenera desde las salidas (run ``search_index``).

La restauración llega en la Fase 10; hasta entonces, se restaura parando la aplicación y copiando los ficheros.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from app import __version__
from app.core.config import Settings

BACKUPS_DIR: Final = "backups"
MANIFEST: Final = "manifest.json"
CONFIG_DB: Final = "config.db"
CACHE_DB: Final = "cache.db"
_STAMP: Final = "%Y%m%dT%H%M%SZ"


@dataclass(frozen=True)
class BackupFile:
    """Base de datos copiada: ruta relativa a ``/data``, tamaño y SHA-256 de la copia."""

    path: str
    size: int
    sha256: str


def databases(settings: Settings) -> list[Path]:
    """``config.db`` y las ``cache.db`` de todas las carpetas de origen de todos los proyectos que existan."""
    data = settings.data_dir
    found = [data / CONFIG_DB] if (data / CONFIG_DB).is_file() else []
    projects = data / "projects"
    if projects.is_dir():
        found.extend(sorted(p for p in projects.rglob(CACHE_DB) if p.is_file() and not p.is_symlink()))
    return found


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(source, timeout=30)) as src, closing(sqlite3.connect(target)) as dst:
        src.backup(dst)
        # La copia hereda WAL: en modo DELETE queda en un único fichero, sin -wal ni -shm al abrirla.
        dst.execute("PRAGMA journal_mode=DELETE")


def create_backup(settings: Settings, *, destination: Path | None = None, keep: int | None = None) -> Path:
    """Copia todas las bases de datos en una carpeta nueva y devuelve su ruta.

    Args:
        destination: Carpeta de las copias (por defecto ``/data/backups``). Conviene llevarlas después fuera del
            servidor: en el mismo volumen no protegen de su pérdida.
        keep: Copias que se conservan en ``destination`` (las más antiguas se borran); ``None`` = todas.

    Raises:
        FileExistsError: Ya hay una copia con la misma marca de tiempo (dos copias en el mismo segundo).
        OSError, sqlite3.Error: No se pudo copiar; la carpeta a medias se borra.
    """
    root = destination or settings.data_dir / BACKUPS_DIR
    target = root / datetime.now(UTC).strftime(_STAMP)
    # Solo el usuario de la aplicación: config.db lleva los hashes de las contraseñas y las sesiones.
    previous = os.umask(0o077)
    try:
        root.mkdir(parents=True, exist_ok=True)
        target.mkdir()
        try:
            files: list[BackupFile] = []
            for source in databases(settings):
                relative = source.relative_to(settings.data_dir).as_posix()
                _copy(source, target / relative)
                copy = target / relative
                files.append(BackupFile(path=relative, size=copy.stat().st_size, sha256=_sha256(copy)))
            manifest = {
                "created_at": datetime.now(UTC).isoformat(),
                "app_version": __version__,
                "files": [asdict(f) for f in files],
            }
            (target / MANIFEST).write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        except BaseException:
            shutil.rmtree(target, ignore_errors=True)  # sin manifiesto, prune no la vería nunca
            raise
    finally:
        os.umask(previous)
    if keep is not None:
        prune(root, keep)
    return target


def backups(root: Path) -> list[Path]:
    """Copias de ``root`` (carpetas con ``manifest.json``), de la más antigua a la más reciente."""
    if not root.is_dir():
        return []
    return sorted(p for p in root.iterdir() if p.is_dir() and not p.is_symlink() and (p / MANIFEST).is_file())


def prune(root: Path, keep: int) -> list[Path]:
    """Borra las copias más antiguas de ``root`` hasta dejar ``keep``; devuelve las borradas."""
    old = backups(root)[: max(0, len(backups(root)) - keep)]
    for path in old:
        shutil.rmtree(path)
    return old


def verify_backup(path: Path) -> list[str]:
    """Problemas de una copia (vacío = correcta): ficheros que faltan, hash distinto o SQLite dañado."""
    manifest_path = path / MANIFEST
    if not manifest_path.is_file():
        return [f"Falta {MANIFEST}."]
    try:
        entries = json.loads(manifest_path.read_text(encoding="utf-8"))["files"]
    except (ValueError, KeyError, TypeError):
        return [f"{MANIFEST} no es válido."]
    problems: list[str] = []
    base = path.resolve()
    for entry in entries:
        copy = path / entry["path"]
        if not copy.resolve().is_relative_to(base):
            problems.append(f"{entry['path']}: ruta fuera de la copia.")
            continue
        if not copy.is_file():
            problems.append(f"Falta {entry['path']}.")
            continue
        if _sha256(copy) != entry["sha256"]:
            problems.append(f"{entry['path']}: el contenido no coincide con el manifiesto.")
            continue
        with closing(sqlite3.connect(f"file:{copy.as_posix()}?mode=ro", uri=True)) as conn:
            try:
                result = conn.execute("PRAGMA integrity_check").fetchone()[0]
            except sqlite3.DatabaseError:
                result = "no es una base de datos SQLite"
        if result != "ok":
            problems.append(f"{entry['path']}: {result}.")
    return problems
