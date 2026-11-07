"""Carpetas guardadas de un proyecto (WB-4.2): son sus carpetas de origen, con su estado en ``scanned_folders``.

Un escaneo elige un subconjunto de ellas (nunca subcarpetas sueltas, porque doc_organize deriva la ruta de cada salida
de la carpeta escaneada) y no pueden estar anidadas. Quitar una carpeta no borra sus salidas.

Cada carpeta guarda las subcarpetas que el escaneo no recorre (1.4.0, G41), relativas a ella. Se pueden cambiar en
cualquier momento, también con un escaneo en marcha: el run copia las de cada carpeta al encolarse (``ScanParams``).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Project, ScannedFolder, User, utcnow
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction, RequestContext
from app.domain.locations.errors import FolderNotFoundError, InvalidRelativePathError, LocationUnavailableError
from app.domain.locations.paths import join_relative, normalize_relative, resolve_within, run_with_timeout
from app.domain.projects import service as projects
from app.domain.projects.errors import ProjectConflictError
from app.domain.projects.folders import nested
from app.domain.projects.service import ProjectAccess
from app.domain.scan.errors import InvalidExclusionError, LastFolderError, ScannedFolderNotFoundError

#: Subcarpetas excluidas como máximo en cada carpeta guardada.
MAX_EXCLUSIONS: Final = 50


@dataclass(frozen=True)
class Exclusion:
    """Subcarpeta excluida del escaneo.

    Attributes:
        subpath: Relativa a la ubicación de origen (como las rutas del explorador).
        exists: Si existe ahora; ``None`` si no se pudo comprobar (carpeta o ubicación no disponibles).
    """

    subpath: str
    exists: bool | None


@dataclass(frozen=True)
class FolderStatus:
    """Una carpeta guardada con su estado, si existe ahora en el origen y sus exclusiones."""

    folder: ScannedFolder
    available: bool
    exclusions: list[Exclusion] = field(default_factory=list)


def _exclusions(folder: ScannedFolder, absolute: Path | None, settings: Settings) -> list[Exclusion]:
    """Exclusiones de ``folder`` relativas a la ubicación; con ``absolute`` (la carpeta resuelta), si existen."""
    stored = list(folder.excluded_subpaths or [])
    if not stored:
        return []
    found: list[bool | None] = [None] * len(stored)
    if absolute is not None:
        base = absolute
        try:
            found = list(
                run_with_timeout(
                    lambda: [os.path.isdir(base / rel) for rel in stored], settings.location_probe_timeout_seconds
                )
            )
        except LocationUnavailableError:
            pass
    return [Exclusion(join_relative(folder.subpath, rel), ok) for rel, ok in zip(stored, found, strict=True)]


def _rows(db: Session, project: Project) -> dict[str, ScannedFolder]:
    rows = db.scalars(select(ScannedFolder).where(ScannedFolder.project_id == project.id))
    return {row.subpath: row for row in rows}


def list_folders(db: Session, project: Project, settings: Settings) -> list[FolderStatus]:
    """Carpetas de origen en orden, con su estado (crea las filas que falten) y su disponibilidad."""
    rows = _rows(db, project)
    if set(rows) != set(project.source_subpaths):
        projects.sync_scanned_folders(db, project, actor_id=None)
        db.commit()
        rows = _rows(db, project)
    location = project.source_location
    root = Path(location.container_path)
    result: list[FolderStatus] = []
    for subpath in project.source_subpaths:
        available = location.status != "unavailable"
        absolute: Path | None = None
        if available:
            try:
                resolved = resolve_within(root, subpath, timeout=settings.location_probe_timeout_seconds)
                available = resolved.absolute.is_dir()
                absolute = resolved.absolute if available else None
            except (FolderNotFoundError, InvalidRelativePathError, LocationUnavailableError, OSError):
                available = False
        row = rows[subpath]
        result.append(FolderStatus(row, available, _exclusions(row, absolute, settings)))
    return result


def _check_idle(db: Session, project: Project) -> None:
    if projects.has_active_run(db, project.id):
        raise ProjectConflictError("Espera a que terminen las ejecuciones del proyecto para cambiar sus carpetas.")


def add_folder(
    db: Session, access: ProjectAccess, subpath: str, *, settings: Settings, actor: User, ctx: RequestContext
) -> ScannedFolder:
    """Añade una carpeta de origen (``owner``), resuelta en la ubicación de origen y sin anidar con las demás.

    Raises:
        ProjectConflictError: Hay ejecuciones en marcha, ya está guardada o se solapa con las salidas de un proyecto.
        NestedFoldersError, InvalidProjectError: Anidada con otra, o ya hay el máximo.
        InvalidRelativePathError, FolderNotFoundError, LocationUnavailableError: Del resolvedor.
    """
    project = access.project
    _check_idle(db, project)
    sources = projects.resolve_sources(project.source_location, [*project.source_subpaths, subpath], settings)
    if sources == project.source_subpaths:
        raise ProjectConflictError("La carpeta ya está guardada en el proyecto.")
    projects.check_destination_free(
        db,
        destination_location_id=project.destination_location_id,
        destination_subpath=project.destination_subpath,
        source_location_id=project.source_location_id,
        source_subpaths=sources,
        exclude_project_id=project.id,
    )
    added = next(s for s in sources if s not in project.source_subpaths)
    project.source_subpaths = sources
    project.updated_at = utcnow()
    projects.sync_scanned_folders(db, project, actor_id=actor.id)
    audit.record(
        db,
        action=AuditAction.SCAN_FOLDER_ADD,
        ctx=ctx,
        actor_id=actor.id,
        target_type="project",
        target_id=project.id,
        details={"subpath": added},
    )
    db.commit()
    return _rows(db, project)[added]


def remove_folder(db: Session, access: ProjectAccess, subpath: str, *, actor: User, ctx: RequestContext) -> bool:
    """Quita una carpeta de origen (``owner``); sus salidas siguen en el destino. Devuelve si ya se había escaneado.

    Raises:
        ScannedFolderNotFoundError: No es una carpeta de origen del proyecto.
        LastFolderError: Es la única.
        ProjectConflictError: Hay ejecuciones en marcha.
    """
    project = access.project
    target = normalize_relative(subpath)
    if target not in project.source_subpaths:
        raise ScannedFolderNotFoundError()
    if len(project.source_subpaths) == 1:
        raise LastFolderError("El proyecto necesita al menos una carpeta de origen.")
    _check_idle(db, project)
    row = _rows(db, project).get(target)
    used = bool(row and row.used)
    project.source_subpaths = [s for s in project.source_subpaths if s != target]
    project.updated_at = utcnow()
    projects.sync_scanned_folders(db, project, actor_id=actor.id)
    audit.record(
        db,
        action=AuditAction.SCAN_FOLDER_REMOVE,
        ctx=ctx,
        actor_id=actor.id,
        target_type="project",
        target_id=project.id,
        details={"subpath": target, "used": used},
    )
    db.commit()
    return used


def _inside(path: str, folder: str) -> bool:
    """Si la ruta relativa ``path`` está estrictamente dentro de ``folder`` (``""`` = la raíz de la ubicación)."""
    return path != folder and (not folder or path.startswith(folder + "/"))


def _check_exclusion(root: Path, folder: Path, target: str, raw: str, settings: Settings) -> str:
    """Valida una exclusión (relativa a la ubicación) y la devuelve relativa a la carpeta guardada ``target``.

    Si existe, se guarda la ruta que da el resolvedor (la real del disco, con sus mayúsculas); si ya no existe, la
    escrita, para poder conservarla y quitarla después.

    Raises:
        InvalidRelativePathError: Sintaxis no válida.
        InvalidExclusionError: Es la propia carpeta, sale de ella, es un enlace o no se puede resolver.
        LocationUnavailableError: La ubicación no responde.
    """
    clean = normalize_relative(raw)
    label = target or "(raíz)"
    if not _inside(clean, target):
        raise InvalidExclusionError(f"«{clean or '(raíz)'}» no es una subcarpeta de «{label}».")
    timeout = settings.location_probe_timeout_seconds
    if not run_with_timeout(lambda: os.path.lexists(root / clean), timeout):
        return clean[len(target) + 1 :] if target else clean
    try:
        resolved = resolve_within(root, clean, timeout=timeout)
    except FolderNotFoundError:
        raise InvalidExclusionError(f"«{clean}» no se puede resolver como una carpeta de la ubicación.") from None
    if resolved.absolute == folder or not resolved.absolute.is_relative_to(folder):
        raise InvalidExclusionError(f"«{clean}» no es una subcarpeta de «{label}».")
    if resolved.relative.casefold() != clean.casefold():
        # El escaneo no sigue enlaces: excluir su destino excluiría otra carpeta.
        raise InvalidExclusionError(f"«{clean}» es un enlace: el escaneo no lo recorre; excluye la carpeta real.")
    return resolved.absolute.relative_to(folder).as_posix()


def _collapse(paths: list[str]) -> list[str]:
    """Sin repetidas ni redundantes (una dentro de otra que ya se excluye), ordenadas."""
    kept: list[str] = []
    for path in sorted(set(paths), key=lambda p: (p.count("/"), p)):
        if not any(nested(path, outer) for outer in kept):
            kept.append(path)
    return sorted(kept, key=lambda p: (p.casefold(), p))


def set_exclusions(
    db: Session,
    access: ProjectAccess,
    subpath: str,
    excluded: list[str],
    *,
    settings: Settings,
    actor: User,
    ctx: RequestContext,
) -> FolderStatus:
    """Sustituye las subcarpetas excluidas de una carpeta guardada (``owner``); rutas relativas a la ubicación.

    No exige que el proyecto esté parado: un escaneo en marcha sigue con la copia que hizo al encolarse.

    Raises:
        ScannedFolderNotFoundError: No es una carpeta de origen del proyecto.
        InvalidExclusionError: Alguna exclusión no es válida o hay más de ``MAX_EXCLUSIONS``.
        InvalidRelativePathError, FolderNotFoundError, LocationUnavailableError: Del resolvedor.
    """
    project = access.project
    target = normalize_relative(subpath)
    if target not in project.source_subpaths:
        raise ScannedFolderNotFoundError()
    if len(excluded) > MAX_EXCLUSIONS:
        raise InvalidExclusionError(f"Se pueden excluir como mucho {MAX_EXCLUSIONS} subcarpetas por carpeta.")
    location = project.source_location
    if location.status == "unavailable":
        raise LocationUnavailableError("La ubicación de origen no está disponible.")
    root = Path(location.container_path)
    folder = resolve_within(root, target, timeout=settings.location_probe_timeout_seconds).absolute
    after = _collapse([_check_exclusion(root, folder, target, raw, settings) for raw in excluded])
    row = _rows(db, project).get(target)
    if row is None:
        projects.sync_scanned_folders(db, project, actor_id=None)
        db.flush()
        row = _rows(db, project)[target]
    before = list(row.excluded_subpaths or [])
    if after != before:
        row.excluded_subpaths = after
        audit.record(
            db,
            action=AuditAction.SCAN_FOLDER_EXCLUSIONS,
            ctx=ctx,
            actor_id=actor.id,
            target_type="project",
            target_id=project.id,
            details={"subpath": target, "before": before, "after": after},
        )
    db.commit()
    return FolderStatus(row, True, _exclusions(row, folder, settings))
