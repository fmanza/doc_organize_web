"""Utilidades de ficheros para las operaciones de proyecto: rutas re-resueltas, recuento, copia y borrado con progreso.

Nada sigue enlaces simbólicos: un enlace dentro de la carpeta del proyecto se cuenta, copia o borra como enlace, nunca
como el árbol al que apunta (mismo criterio que la web integrada al calcular el impacto).
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from app.db.models import Location, Project
from app.domain.locations.errors import FolderNotFoundError, InvalidRelativePathError, LocationUnavailableError
from app.domain.locations.paths import ResolvedPath, resolve_within
from app.domain.projects.service import state_dir
from app.jobs.context import JobContext, JobFailed


@dataclass(frozen=True)
class ProjectPaths:
    """Carpetas del proyecto en el contenedor, resueltas de nuevo en el worker.

    Attributes:
        output: Carpeta de salidas en la ubicación destino.
        state: Carpeta de estado en ``DOW_DATA_DIR/projects/<id>``.
    """

    output: ResolvedPath
    state: Path


@dataclass(frozen=True)
class TreeSize:
    """Ficheros y bytes de un árbol (los enlaces cuentan como fichero de tamaño 0)."""

    files: int = 0
    bytes: int = 0


def resolve_in(location: Location, relative: str, ctx: JobContext) -> ResolvedPath:
    """``relative`` dentro de ``location`` con el resolvedor de ubicaciones.

    Raises:
        JobFailed: La ubicación no responde o la carpeta ya no existe.
    """
    try:
        return resolve_within(
            Path(location.container_path), relative, timeout=ctx.settings.location_probe_timeout_seconds
        )
    except LocationUnavailableError:
        raise JobFailed("location_unavailable", f"La ubicación «{location.name}» no está disponible.") from None
    except (FolderNotFoundError, InvalidRelativePathError):
        raise JobFailed("folder_missing", f"La carpeta «{relative}» ya no existe en «{location.name}».") from None


def project_paths(project: Project, ctx: JobContext) -> ProjectPaths:
    """Salidas y estado del proyecto.

    Raises:
        JobFailed: La carpeta de salidas no está disponible, o se ha sustituido por un enlace (o lo es alguna carpeta
            superior): al resolverla daría otra carpeta y un borrado alcanzaría ficheros ajenos al proyecto.
    """
    output = resolve_in(project.destination_location, project.destination_subpath, ctx)
    if not output.relative or output.relative != project.destination_subpath:
        raise JobFailed("folder_replaced", "La carpeta de salidas del proyecto ya no es la registrada; no se toca.")
    return ProjectPaths(output=output, state=state_dir(ctx.settings, project.id))


def require_rw(location: Location) -> None:
    """La ubicación sigue siendo ``rw`` (el admin pudo cambiarla tras encolar).

    Raises:
        JobFailed: Es de solo lectura.
    """
    if location.access != "rw":
        raise JobFailed("location_read_only", f"La ubicación «{location.name}» es de solo lectura.")


def measure(root: Path, ctx: JobContext, phase: str) -> TreeSize:
    """Cuenta ficheros y bytes bajo ``root`` sin seguir enlaces, con progreso y cancelación."""
    if not root.exists():
        return TreeSize()
    files = size = 0
    for current, dirnames, filenames in os.walk(root, followlinks=False):
        ctx.check_cancelled()
        for name in filenames + [d for d in dirnames if os.path.islink(os.path.join(current, d))]:
            files += 1
            try:
                stat = os.lstat(os.path.join(current, name))
            except OSError:
                continue
            if not os.path.islink(os.path.join(current, name)):
                size += stat.st_size
        ctx.progress(phase, files)
    return TreeSize(files=files, bytes=size)


def delete_tree(root: Path, ctx: JobContext, phase: str, *, total: int | None = None) -> list[str]:
    """Borra ``root`` entero sin seguir enlaces. Devuelve las rutas relativas que no se pudieron borrar.

    Cada entrada de primer nivel se borra con ``shutil.rmtree``, que en Linux trabaja con descriptores y no sigue un
    enlace aunque alguien sustituya una carpeta por uno a mitad del borrado (``rmtree.avoids_symlink_attacks``). No se
    interrumpe por cancelación: dejar un árbol a medio borrar es peor que terminar (quien llama lo marca como fase
    crítica).
    """
    failed: list[str] = []

    def _failed(_: object, path: str, __: BaseException) -> None:
        failed.append(Path(path).relative_to(root).as_posix() if Path(path).is_relative_to(root) else ".")

    if not root.exists() and not root.is_symlink():
        return failed
    entries = list(os.scandir(root))
    for done, entry in enumerate(entries, start=1):
        if entry.is_dir(follow_symlinks=False):
            shutil.rmtree(entry.path, onexc=_failed)
        else:
            try:
                os.unlink(entry.path)
            except OSError:
                failed.append(entry.name)
        ctx.progress(phase, done, len(entries))
    try:
        root.rmdir()
    except OSError:
        if root.exists():
            failed.append(".")
    return failed


def copy_tree(source: Path, target: Path, ctx: JobContext, phase: str, *, total: int) -> int:
    """Copia ``source`` en ``target`` (nueva) con metadatos, enlaces como enlaces, progreso y cancelación.

    Returns:
        Ficheros copiados.

    Raises:
        JobCancelled: Se pidió cancelar (quien llama borra la copia parcial).
        OSError: Fallo de E/S (quien llama borra la copia parcial).
    """
    target.mkdir()
    copied = 0
    for current, dirnames, filenames in os.walk(source, followlinks=False):
        rel = Path(current).relative_to(source)
        for name in dirnames:
            src = Path(current) / name
            if src.is_symlink():
                os.symlink(os.readlink(src), target / rel / name)
                copied += 1
            else:
                (target / rel / name).mkdir()
        for name in filenames:
            ctx.check_cancelled()
            shutil.copy2(Path(current) / name, target / rel / name, follow_symlinks=False)
            copied += 1
            ctx.progress(phase, copied, total)
    return copied
