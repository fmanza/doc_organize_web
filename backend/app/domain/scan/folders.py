"""Carpetas guardadas de un proyecto (WB-4.2): son sus carpetas de origen, con su estado en ``scanned_folders``.

Un escaneo elige un subconjunto de ellas (nunca subcarpetas sueltas, porque doc_organize deriva la ruta de cada salida
de la carpeta escaneada) y no pueden estar anidadas. Quitar una carpeta no borra sus salidas.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Project, ScannedFolder, User, utcnow
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction, RequestContext
from app.domain.locations.errors import FolderNotFoundError, InvalidRelativePathError, LocationUnavailableError
from app.domain.locations.paths import normalize_relative, resolve_within
from app.domain.projects import service as projects
from app.domain.projects.errors import ProjectConflictError
from app.domain.projects.service import ProjectAccess
from app.domain.scan.errors import LastFolderError, ScannedFolderNotFoundError


@dataclass(frozen=True)
class FolderStatus:
    """Una carpeta guardada con su estado y si existe ahora en el origen."""

    folder: ScannedFolder
    available: bool


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
        if available:
            try:
                resolved = resolve_within(root, subpath, timeout=settings.location_probe_timeout_seconds)
                available = resolved.absolute.is_dir()
            except (FolderNotFoundError, InvalidRelativePathError, LocationUnavailableError, OSError):
                available = False
        result.append(FolderStatus(rows[subpath], available))
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
