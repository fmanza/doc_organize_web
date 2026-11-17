"""Versiones del manifiesto de taxonomía (1.8.0): guardar lo que había antes de cada cambio y recortar a las últimas.

Cada cambio del manifiesto (guardar, borrar, restaurar, vaciar el histórico) guarda **antes** una versión con el texto
que había en el disco, para poder deshacerlo. Se conservan las ``MAX_MANIFEST_VERSIONS`` últimas por proyecto.

También da el ``etag`` del manifiesto (concurrencia optimista con ``If-Match``) y un cerrojo por proyecto en el proceso
para la sección crítica «leer → versión → escribir».
"""

from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.models import ManifestVersionAction, ProjectManifestVersion, User
from app.domain.context.errors import ManifestVersionNotFoundError
from app.integrations.doc_organize import context as library

#: Versiones que se conservan por proyecto (las más recientes).
MAX_MANIFEST_VERSIONS: Final = 5
#: ``etag`` cuando el proyecto no tiene manifiesto.
NO_MANIFEST_ETAG: Final = "none"

_LOCKS: dict[int, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def manifest_etag(markdown: str | None) -> str:
    """SHA-256 del texto del manifiesto (saltos de línea normalizados a ``\\n``), o ``"none"`` si no hay.

    Se normaliza porque la librería escribe con el salto de línea del sistema y el navegador envía ``\\n``.
    """
    if markdown is None:
        return NO_MANIFEST_ETAG
    return hashlib.sha256(normalize(markdown).encode("utf-8")).hexdigest()


def normalize(markdown: str) -> str:
    """El texto con saltos de línea ``\\n`` (para comparar el guardado con el del disco)."""
    return markdown.replace("\r\n", "\n")


def project_lock(project_id: int) -> threading.Lock:
    """Cerrojo del manifiesto del proyecto en este proceso (dos peticiones a la vez no se mezclan)."""
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(project_id, threading.Lock())


def _counts(markdown: str | None) -> tuple[int | None, int | None]:
    if markdown is None:
        return None, None
    try:
        info = library.parse_template(markdown)
    except library.TemplateInvalidError:
        return None, None
    return len(info.domains), len(info.material_types)


def add_version(
    db: Session, project_id: int, markdown: str | None, action: ManifestVersionAction, *, actor_id: int | None
) -> ProjectManifestVersion:
    """Añade la versión ``markdown`` (lo que había antes de ``action``) y recorta a las últimas. No confirma."""
    domains, material_types = _counts(markdown)
    version = ProjectManifestVersion(
        project_id=project_id,
        created_by=actor_id,
        action=action,
        markdown=markdown,
        domains=domains,
        material_types=material_types,
    )
    db.add(version)
    db.flush()
    stale = (
        select(ProjectManifestVersion.id)
        .where(ProjectManifestVersion.project_id == project_id)
        .order_by(ProjectManifestVersion.created_at.desc(), ProjectManifestVersion.id.desc())
        .offset(MAX_MANIFEST_VERSIONS)
    )
    ids = list(db.scalars(stale))
    if ids:
        db.execute(delete(ProjectManifestVersion).where(ProjectManifestVersion.id.in_(ids)))
    return version


@dataclass(frozen=True)
class VersionSummary:
    """Una versión en la lista (sin el texto)."""

    id: int
    created_at: datetime
    created_by: str | None
    action: str
    empty: bool
    valid: bool
    domains: int | None
    material_types: int | None


def list_versions(db: Session, project_id: int) -> list[VersionSummary]:
    """Versiones del proyecto, de la más reciente a la más antigua, con el nombre visible de quien hizo el cambio."""
    rows = db.execute(
        select(ProjectManifestVersion, User.display_name)
        .outerjoin(User, User.id == ProjectManifestVersion.created_by)
        .where(ProjectManifestVersion.project_id == project_id)
        .order_by(ProjectManifestVersion.created_at.desc(), ProjectManifestVersion.id.desc())
    ).all()
    return [
        VersionSummary(
            id=version.id,
            created_at=version.created_at,
            created_by=name,
            action=version.action,
            empty=version.markdown is None,
            valid=version.markdown is not None and version.domains is not None,
            domains=version.domains,
            material_types=version.material_types,
        )
        for version, name in rows
    ]


def get_version(db: Session, project_id: int, version_id: int) -> ProjectManifestVersion:
    """La versión ``version_id`` **de este proyecto** (una de otro proyecto da el mismo 404).

    Raises:
        ManifestVersionNotFoundError: No existe en el proyecto.
    """
    version = db.scalar(
        select(ProjectManifestVersion).where(
            ProjectManifestVersion.project_id == project_id, ProjectManifestVersion.id == version_id
        )
    )
    if version is None:
        raise ManifestVersionNotFoundError()
    return version


def latest_version_at(db: Session, project_id: int) -> datetime | None:
    """Fecha de la versión más reciente (cuándo cambió el manifiesto por última vez desde la app)."""
    return db.scalar(
        select(func.max(ProjectManifestVersion.created_at)).where(ProjectManifestVersion.project_id == project_id)
    )
