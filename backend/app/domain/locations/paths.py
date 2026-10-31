"""Resolución segura de rutas dentro de una raíz (ADR-007, ``filesystem.instructions.md``).

Es el **único** punto que convierte una ruta que llega por la API en una ruta del sistema de ficheros:

1. Rechazo sintáctico: solo rutas relativas con ``/``; nada de rutas absolutas, UNC, letras de unidad, ``\\``, ``..``
   ni bytes nulos (400).
2. ``resolve(strict=True)`` y ``is_relative_to(raíz_resuelta)``: un enlace simbólico que sale de la raíz se rechaza.
3. Fuera de la raíz o inexistente dan el **mismo** error (404), para no revelar qué existe fuera.

Las operaciones de E/S se ejecutan con un timeout: un montaje de red colgado da ``LocationUnavailableError`` (503) en
lugar de bloquear la petición. El hilo colgado no se puede matar; queda en el *pool* hasta que el sistema operativo
devuelva el control.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final

from app.domain.locations.errors import FolderNotFoundError, InvalidRelativePathError, LocationUnavailableError

MAX_RELATIVE_PATH = 4096
_DRIVE: Final = re.compile(r"^[A-Za-z]:")
# Pocas operaciones simultáneas de E/S en montajes: si uno se cuelga, no agota los hilos del servidor.
_IO_POOL: Final = ThreadPoolExecutor(max_workers=8, thread_name_prefix="dow-fs")


@dataclass(frozen=True)
class ResolvedPath:
    """Ruta validada dentro de una raíz.

    Attributes:
        root: Raíz resuelta (la carpeta de la ubicación).
        absolute: Ruta resuelta, siempre dentro de ``root``.
        relative: Ruta relativa a ``root`` con ``/`` (``""`` para la propia raíz).
    """

    root: Path
    absolute: Path
    relative: str


def run_with_timeout[T](func: Callable[[], T], timeout: float) -> T:
    """Ejecuta ``func`` en el *pool* de E/S y espera como mucho ``timeout`` segundos.

    Raises:
        LocationUnavailableError: Se agotó el tiempo o falló la E/S del montaje.
    """
    future = _IO_POOL.submit(func)
    try:
        return future.result(timeout=timeout)
    except FutureTimeout:
        raise LocationUnavailableError("La ubicación no responde a tiempo.") from None


def normalize_relative(path: str | None) -> str:
    """Valida la sintaxis de una ruta relativa y la devuelve normalizada (``""`` = la raíz).

    Raises:
        InvalidRelativePathError: Absoluta, UNC, con unidad, con ``\\``, con ``..``, con bytes nulos o demasiado larga.
    """
    raw = (path or "").strip()
    if len(raw) > MAX_RELATIVE_PATH or "\x00" in raw or "\\" in raw or raw.startswith("/") or _DRIVE.match(raw):
        raise InvalidRelativePathError("Usa una ruta relativa a la ubicación, con «/» como separador.")
    parts = [part for part in PurePosixPath(raw).parts if part not in ("", ".")]
    if ".." in parts:
        raise InvalidRelativePathError("La ruta no puede contener «..».")
    return "/".join(parts)


def resolve_within(root: Path, relative: str | None, *, timeout: float) -> ResolvedPath:
    """Resuelve ``relative`` dentro de ``root`` siguiendo enlaces y comprueba que sigue dentro y es una carpeta.

    Raises:
        InvalidRelativePathError: Sintaxis no válida.
        FolderNotFoundError: No existe, no es una carpeta o queda fuera de ``root`` (mismo error).
        LocationUnavailableError: La raíz no responde o no es accesible.
    """
    clean = normalize_relative(relative)

    def _resolve() -> ResolvedPath:
        try:
            base = root.resolve(strict=True)
        except OSError as exc:
            raise LocationUnavailableError("No se puede acceder a la ubicación.") from exc
        try:
            target = (base / clean).resolve(strict=True)
        except OSError:
            raise FolderNotFoundError() from None
        if not target.is_relative_to(base) or not target.is_dir():
            raise FolderNotFoundError()
        rel = target.relative_to(base).as_posix()
        return ResolvedPath(root=base, absolute=target, relative="" if rel == "." else rel)

    return run_with_timeout(_resolve, timeout)


def list_subfolders(resolved: ResolvedPath, *, timeout: float) -> list[str]:
    """Nombres de las subcarpetas inmediatas de ``resolved``, ordenados sin distinguir mayúsculas.

    Se omiten las entradas ilegibles y los enlaces simbólicos que salen de la raíz.

    Raises:
        LocationUnavailableError: No se puede leer la carpeta o no responde a tiempo.
    """

    def _list() -> list[str]:
        names: list[str] = []
        try:
            with os.scandir(resolved.absolute) as entries:
                for entry in entries:
                    try:
                        if not entry.is_dir(follow_symlinks=True):
                            continue
                        if entry.is_symlink() and not Path(entry.path).resolve().is_relative_to(resolved.root):
                            continue
                    except OSError:
                        continue
                    names.append(entry.name)
        except OSError as exc:
            raise LocationUnavailableError("No se puede leer la carpeta.") from exc
        return sorted(names, key=str.casefold)

    return run_with_timeout(_list, timeout)


def join_relative(parent: str, name: str) -> str:
    """Ruta relativa de ``name`` dentro de ``parent``."""
    return f"{parent}/{name}" if parent else name


def parent_of(relative: str) -> str | None:
    """Ruta relativa de la carpeta superior, o ``None`` en la raíz."""
    if not relative:
        return None
    parent = PurePosixPath(relative).parent.as_posix()
    return "" if parent == "." else parent
