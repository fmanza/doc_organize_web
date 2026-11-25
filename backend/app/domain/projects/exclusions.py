"""Exclusiones del proyecto y «exclusión efectiva» (web 2.7, ADR-017).

Una carpeta excluida queda fuera del proyecto a todos los efectos: no se escanea y lo que siga en la caché de un escaneo
anterior no se usa en duplicados, contexto (y lo que lo lee: borradores, agentes, calidad, entrega) ni exportaciones de
la caché. La exclusión efectiva de un proyecto es la unión de:

- las **rutas y patrones del proyecto** (``projects.excluded_paths`` relativas a la ubicación de origen e
  ``ignore_patterns``, que gestiona el ``owner``);
- las **subcarpetas excluidas de cada carpeta guardada** (``scanned_folders.excluded_subpaths``, 1.4.0);
- los **patrones de la ubicación** de origen (``locations.ignore_patterns``, que fija el admin);
- el **preset de carpetas de sistema** (``SYSTEM_PATTERNS``), si el proyecto lo tiene activado.

Las rutas se guardan y se devuelven siempre relativas a la ubicación; solo el worker las une con la raíz real.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from fnmatch import translate
from pathlib import Path
from typing import Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Project, ScannedFolder, User
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction, RequestContext
from app.domain.locations.errors import LocationUnavailableError
from app.domain.locations.paths import join_relative, normalize_relative, resolve_within, run_with_timeout
from app.domain.locations.service import check_ignore_patterns
from app.domain.projects.service import ProjectAccess
from app.domain.scan.errors import InvalidExclusionError
from app.domain.scan.folders import check_exclusion, collapse_exclusions

#: Carpetas y ficheros de sistema de NAS (Synology, QNAP, NetApp) y de Windows que el preset excluye. Todos son
#: patrones de nombre válidos para ``ScanOptions.ignore_patterns`` (sin separadores, como mucho 64 caracteres).
SYSTEM_PATTERNS: Final[tuple[str, ...]] = (
    "#recycle",
    "@eaDir",
    ".snapshot",
    "~snapshot",
    "$RECYCLE.BIN",
    "System Volume Information",
    "Thumbs.db",
    "desktop.ini",
    "~$*",
)
#: Rutas excluidas como mucho en el proyecto.
MAX_PROJECT_EXCLUSIONS: Final = 100
#: Patrones de nombre como mucho en el proyecto (como en una ubicación).
MAX_PROJECT_PATTERNS: Final = 30
#: Exclusiones como mucho en una carpeta al escanear: las suyas más las del proyecto que caen en ella (A4).
MAX_EFFECTIVE_PER_FOLDER: Final = 150
#: Patrones como mucho al escanear: ubicación + proyecto + preset (A4).
MAX_EFFECTIVE_PATTERNS: Final = 100
#: Patrones que vaciarían el proyecto: solo se rechazan en el proyecto (las ubicaciones no cambian).
_MATCH_ALL: Final = frozenset({"*", "**", "*.*", "?*", "*?"})


@dataclass(frozen=True)
class EffectiveExclusion:
    """Exclusión efectiva de un proyecto: rutas relativas a la ubicación de origen y patrones de nombre."""

    paths: list[str] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)

    def for_folder(self, folder: str) -> list[str]:
        """Rutas que caen dentro de la carpeta guardada ``folder``, relativas a ella (formato de ``ScanParams``)."""
        prefix = f"{folder}/" if folder else ""
        return [path[len(prefix) :] for path in self.paths if path != folder and path.startswith(prefix)]

    def fingerprint(self) -> str:
        """Huella estable (orden indiferente): cambia si cambia cualquier ruta o patrón."""
        payload = json.dumps([sorted(self.paths), sorted(self.patterns)], ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ProjectExclusionPath:
    """Ruta excluida del proyecto, relativa a la ubicación; ``exists`` es ``None`` si no se pudo comprobar."""

    path: str
    exists: bool | None


@dataclass(frozen=True)
class ProjectExclusions:
    """Exclusiones propias del proyecto (lo que edita el ``owner``)."""

    excluded: list[ProjectExclusionPath]
    ignore_patterns: list[str]
    exclude_system_folders: bool


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(values))


def check_project_patterns(patterns: Sequence[str]) -> list[str]:
    """Valida los patrones del proyecto: las reglas de una ubicación y, además, ninguno que lo excluya todo.

    Raises:
        InvalidIgnorePatternsError: Demasiados, vacíos, con separadores o demasiado largos (las de la ubicación).
        InvalidExclusionError: Un patrón que excluiría todo el proyecto (``*``, ``*.*``…).
    """
    clean = check_ignore_patterns([p.strip() for p in patterns])
    for pattern in clean:
        if pattern in _MATCH_ALL or set(pattern) <= {"*", "?", "."}:
            raise InvalidExclusionError(f"«{pattern}» excluiría todo el proyecto.")
    return clean


def effective(db: Session, project: Project) -> EffectiveExclusion:
    """Exclusión efectiva actual del proyecto (proyecto ∪ carpetas guardadas ∪ ubicación ∪ preset)."""
    rows = db.scalars(select(ScannedFolder).where(ScannedFolder.project_id == project.id))
    paths = list(project.excluded_paths or [])
    for row in rows:
        if row.subpath in project.source_subpaths:
            paths.extend(join_relative(row.subpath, rel) for rel in row.excluded_subpaths or [])
    location = project.source_location
    patterns = [
        *(location.ignore_patterns or [] if location is not None else []),
        *(project.ignore_patterns or []),
        *(SYSTEM_PATTERNS if project.exclude_system_folders else ()),
    ]
    return EffectiveExclusion(paths=collapse_exclusions(paths), patterns=_unique(patterns))


def _folder_of(path: str, folders: Sequence[str]) -> str | None:
    """Carpeta guardada que contiene estrictamente ``path``, o ``None``."""
    for folder in folders:
        if path != folder and (not folder or path.startswith(folder + "/")):
            return folder
    return None


def _exists(project: Project, paths: list[str], settings: Settings) -> list[bool | None]:
    location = project.source_location
    if location is None or location.status == "unavailable" or not paths:
        return [None] * len(paths)
    root = Path(location.container_path)
    try:
        return list(
            run_with_timeout(
                lambda: [os.path.isdir(root / path) for path in paths], settings.location_probe_timeout_seconds
            )
        )
    except LocationUnavailableError:
        return [None] * len(paths)


def get_exclusions(project: Project, settings: Settings) -> ProjectExclusions:
    """Exclusiones propias del proyecto, con si cada ruta existe ahora."""
    paths = list(project.excluded_paths or [])
    found = _exists(project, paths, settings)
    return ProjectExclusions(
        excluded=[ProjectExclusionPath(p, ok) for p, ok in zip(paths, found, strict=True)],
        ignore_patterns=list(project.ignore_patterns or []),
        exclude_system_folders=project.exclude_system_folders,
    )


def check_paths(project: Project, raw_paths: Sequence[str], settings: Settings, *, limit: int) -> list[str]:
    """Valida rutas excluidas (relativas a la ubicación) dentro de alguna carpeta guardada; las devuelve colapsadas.

    Se usa para las del proyecto y para las de un solo análisis de duplicados (``extra_excluded_paths``). Si existen,
    se guarda la ruta real del disco; si no, la escrita.

    Raises:
        InvalidExclusionError: Demasiadas, fuera de las carpetas del proyecto, la propia carpeta o un enlace.
        InvalidRelativePathError: Sintaxis no válida.
        LocationUnavailableError: La ubicación no responde.
    """
    if len(raw_paths) > limit:
        raise InvalidExclusionError(f"Se pueden excluir como mucho {limit} carpetas.")
    if not raw_paths:
        return []
    location = project.source_location
    if location is None or location.status == "unavailable":
        raise LocationUnavailableError("La ubicación de origen no está disponible.")
    root = Path(location.container_path)
    resolved_root = resolve_within(root, "", timeout=settings.location_probe_timeout_seconds).absolute
    folders = sorted(project.source_subpaths, key=len, reverse=True)
    checked: list[str] = []
    for raw in raw_paths:
        clean = normalize_relative(raw)
        folder = _folder_of(clean, folders)
        if folder is None:
            raise InvalidExclusionError(f"«{clean or '(raíz)'}» no está dentro de ninguna carpeta del proyecto.")
        # Relativa a la raíz de la ubicación: la misma validación que las de una carpeta guardada (``target`` = raíz).
        checked.append(check_exclusion(root, resolved_root, "", clean, settings))
    return collapse_exclusions(checked)


def set_exclusions(
    db: Session,
    access: ProjectAccess,
    *,
    excluded: Sequence[str],
    ignore_patterns: Sequence[str],
    exclude_system_folders: bool,
    settings: Settings,
    actor: User,
    ctx: RequestContext,
) -> ProjectExclusions:
    """Sustituye las exclusiones del proyecto (``owner``). No exige que esté parado: los runs usan su copia.

    Raises:
        InvalidExclusionError, InvalidIgnorePatternsError, InvalidRelativePathError, LocationUnavailableError.
    """
    project = access.project
    paths = check_paths(project, excluded, settings, limit=MAX_PROJECT_EXCLUSIONS)
    if len(ignore_patterns) > MAX_PROJECT_PATTERNS:
        raise InvalidExclusionError(f"Se admiten como mucho {MAX_PROJECT_PATTERNS} patrones.")
    patterns = check_project_patterns(ignore_patterns)
    before = {
        "excluded": list(project.excluded_paths or []),
        "ignore_patterns": list(project.ignore_patterns or []),
        "exclude_system_folders": project.exclude_system_folders,
    }
    after = {"excluded": paths, "ignore_patterns": patterns, "exclude_system_folders": exclude_system_folders}
    if after != before:
        project.excluded_paths = paths
        project.ignore_patterns = patterns
        project.exclude_system_folders = exclude_system_folders
        audit.record(
            db,
            action=AuditAction.PROJECT_EXCLUSIONS,
            ctx=ctx,
            actor_id=actor.id,
            target_type="project",
            target_id=project.id,
            details={"before": before, "after": after},
        )
    db.commit()
    return get_exclusions(project, settings)


class PathFilter:
    """Si una ruta absoluta de la caché queda excluida (worker, ADR-017).

    Mismo criterio que ``EntryFilter.covers_cached`` de doc_organize (que es de uso interno y no se importa, como
    ``ExclusionMatcher`` de la vista previa de «forzar»): rutas comparadas con ``normcase`` por prefijo, y patrones
    ``fnmatch`` sobre el nombre en minúsculas de cada tramo por debajo de la carpeta escaneada que la contiene.
    """

    def __init__(self, roots: Iterable[Path], excluded: Iterable[Path], patterns: Sequence[str]) -> None:
        self._roots = sorted((os.path.normcase(str(r)) for r in roots), key=len, reverse=True)
        self._excluded = [os.path.normcase(str(path)).rstrip(os.sep) for path in excluded]
        self._regex = re.compile("|".join(translate(p.lower()) for p in patterns)) if patterns else None

    @property
    def empty(self) -> bool:
        return not self._excluded and self._regex is None

    def covers(self, path: str) -> bool:
        key = os.path.normcase(path)
        if any(key == ex or key.startswith(ex + os.sep) for ex in self._excluded):
            return True
        if self._regex is None:
            return False
        for root in self._roots:
            prefix = root.rstrip(os.sep) + os.sep
            if key.startswith(prefix):
                return any(self._regex.match(part.lower()) for part in key[len(prefix) :].split(os.sep) if part)
        return False


def path_filter(location_root: Path, roots: Iterable[Path], exclusion: EffectiveExclusion) -> PathFilter:
    """``PathFilter`` de una exclusión efectiva: une las rutas relativas con la raíz real de la ubicación."""
    return PathFilter(roots, [location_root / path for path in exclusion.paths], exclusion.patterns)
