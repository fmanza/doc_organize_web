"""Casos de uso de ubicaciones: registro, edición, borrado, sondeo y explorador de carpetas (ADR-007)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import (
    DEFAULT_TENANT_ID,
    Location,
    LocationAccess,
    LocationKind,
    LocationUsage,
    User,
    utcnow,
)
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction, RequestContext
from app.domain.locations.errors import (
    FolderNotFoundError,
    InvalidLocationPathError,
    InvalidRelativePathError,
    LocationConflictError,
    LocationNotFoundError,
    LocationUnavailableError,
)
from app.domain.locations.paths import (
    ResolvedPath,
    join_relative,
    list_subfolders,
    parent_of,
    resolve_within,
    run_with_timeout,
)
from app.domain.locations.probe import probe


@dataclass(frozen=True)
class FolderPage:
    """Página de subcarpetas de una carpeta.

    Attributes:
        path: Ruta relativa de la carpeta listada (``""`` = la raíz).
        parent: Ruta relativa de la carpeta superior, o ``None`` en la raíz.
        names: Nombres de las subcarpetas de la página.
        total: Total de subcarpetas.
    """

    path: str
    parent: str | None
    names: list[str]
    total: int

    def items(self) -> list[tuple[str, str]]:
        """``(nombre, ruta_relativa)`` de cada subcarpeta."""
        return [(name, join_relative(self.path, name)) for name in self.names]


@dataclass(frozen=True)
class LocationChanges:
    """Cambios de un ``PATCH``; ``None`` = sin cambio. ``container_path`` no se puede cambiar."""

    name: str | None = None
    display_path: str | None = None
    kind: LocationKind | None = None
    usage: LocationUsage | None = None
    access: LocationAccess | None = None


def list_locations(db: Session, *, limit: int, offset: int) -> tuple[list[Location], int]:
    """Ubicaciones visibles ordenadas por nombre (todas son ``global`` hasta la Fase 9)."""
    query = select(Location).where(Location.tenant_id == DEFAULT_TENANT_ID)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(func.lower(Location.name)).limit(limit).offset(offset)).all()
    return list(rows), total


def get_location(db: Session, location_id: int) -> Location:
    """Ubicación visible por id.

    Raises:
        LocationNotFoundError: No existe o no es visible.
    """
    location = db.get(Location, location_id)
    if location is None or location.tenant_id != DEFAULT_TENANT_ID:
        raise LocationNotFoundError()
    return location


def _validate_container_path(db: Session, relative_to_root: str, settings: Settings) -> Path:
    """Carpeta bajo ``DOW_LOCATIONS_ROOT`` para una ubicación nueva, resuelta y sin solapes.

    Raises:
        InvalidLocationPathError: Fuera de la raíz, inexistente, la propia raíz, dentro de ``data``/``workspace`` o
            solapada con otra ubicación.
    """
    try:
        resolved = resolve_within(
            settings.locations_root, relative_to_root, timeout=settings.location_probe_timeout_seconds
        )
    except (InvalidRelativePathError, LocationUnavailableError) as exc:
        raise InvalidLocationPathError(exc.detail) from None
    except FolderNotFoundError:
        raise InvalidLocationPathError("La carpeta no existe bajo la raíz de ubicaciones.") from None
    if not resolved.relative:
        raise InvalidLocationPathError("Elige una subcarpeta, no la raíz de ubicaciones.")
    path = resolved.absolute
    for reserved in (settings.data_dir, settings.workspace_dir):
        base = Path(reserved).resolve()
        if path.is_relative_to(base) or base.is_relative_to(path):
            raise InvalidLocationPathError("La carpeta no puede incluir los volúmenes de datos de la aplicación.")
    for (other,) in db.execute(select(Location.container_path)):
        other_path = Path(other)
        if path == other_path:
            raise LocationConflictError("Ya hay una ubicación con esa carpeta.")
        if path.is_relative_to(other_path) or other_path.is_relative_to(path):
            raise InvalidLocationPathError("La carpeta se solapa con otra ubicación.")
    return path


def _name_taken(db: Session, name: str, *, exclude_id: int | None = None) -> bool:
    query = select(Location.id).where(
        Location.tenant_id == DEFAULT_TENANT_ID, func.lower(Location.name) == name.strip().lower()
    )
    if exclude_id is not None:
        query = query.where(Location.id != exclude_id)
    return db.scalar(query) is not None


def _apply_probe(location: Location, settings: Settings) -> None:
    result = probe(Path(location.container_path), access=location.access, settings=settings)
    location.status = result.status
    location.status_reasons = result.reasons
    location.latency_ms = result.latency_ms
    location.free_bytes = result.free_bytes
    location.writable = result.writable
    location.probed_at = utcnow()


def create_location(
    db: Session,
    *,
    name: str,
    path: str,
    display_path: str | None,
    kind: LocationKind,
    usage: LocationUsage,
    access: LocationAccess,
    settings: Settings,
    actor: User,
    ctx: RequestContext,
) -> Location:
    """Registra una ubicación con la carpeta ``path`` (relativa a ``DOW_LOCATIONS_ROOT``) y la sondea.

    Raises:
        LocationConflictError: Nombre o carpeta ya registrados.
        InvalidLocationPathError: Carpeta no válida.
    """
    if _name_taken(db, name):
        raise LocationConflictError("Ya hay una ubicación con ese nombre.")
    container_path = _validate_container_path(db, path, settings)
    location = Location(
        name=name.strip(),
        container_path=str(container_path),
        display_path=(display_path or "").strip() or None,
        kind=kind,
        usage=usage,
        access=access,
    )
    _apply_probe(location, settings)
    db.add(location)
    db.flush()
    audit.record(
        db,
        action=AuditAction.LOCATION_CREATE,
        ctx=ctx,
        actor_id=actor.id,
        target_type="location",
        target_id=location.id,
        details={"name": location.name, "usage": usage, "access": access, "status": location.status},
    )
    db.commit()
    return location


def update_location(
    db: Session, location: Location, changes: LocationChanges, *, settings: Settings, actor: User, ctx: RequestContext
) -> Location:
    """Aplica ``changes``; si cambia el acceso, vuelve a sondear.

    Raises:
        LocationConflictError: El nombre nuevo ya existe.
    """
    changed: list[str] = []
    if changes.name is not None and changes.name.strip() != location.name:
        if _name_taken(db, changes.name, exclude_id=location.id):
            raise LocationConflictError("Ya hay una ubicación con ese nombre.")
        location.name = changes.name.strip()
        changed.append("name")
    if changes.display_path is not None and (changes.display_path.strip() or None) != location.display_path:
        location.display_path = changes.display_path.strip() or None
        changed.append("display_path")
    for field_name in ("kind", "usage", "access"):
        value = getattr(changes, field_name)
        if value is not None and value != getattr(location, field_name):
            setattr(location, field_name, value)
            changed.append(field_name)
    if "access" in changed:
        _apply_probe(location, settings)
    if changed:
        audit.record(
            db,
            action=AuditAction.LOCATION_UPDATE,
            ctx=ctx,
            actor_id=actor.id,
            target_type="location",
            target_id=location.id,
            details={"fields": changed},
        )
    db.commit()
    return location


def delete_location(db: Session, location: Location, *, actor: User, ctx: RequestContext) -> None:
    """Borra el registro de la ubicación (nunca la carpeta).

    Raises:
        LocationConflictError: Algún proyecto la usa como origen o destino (también los borrados, que conservan su
            historial de ejecuciones).
    """
    from app.domain.projects.service import projects_using_location

    if projects_using_location(db, location.id):
        raise LocationConflictError("Hay proyectos que usan esta ubicación.")
    audit.record(
        db,
        action=AuditAction.LOCATION_DELETE,
        ctx=ctx,
        actor_id=actor.id,
        target_type="location",
        target_id=location.id,
        details={"name": location.name},
    )
    db.delete(location)
    db.commit()


def probe_location(
    db: Session, location: Location, *, settings: Settings, actor: User, ctx: RequestContext
) -> Location:
    """Vuelve a sondear la ubicación y guarda el estado."""
    _apply_probe(location, settings)
    audit.record(
        db,
        action=AuditAction.LOCATION_PROBE,
        ctx=ctx,
        actor_id=actor.id,
        target_type="location",
        target_id=location.id,
        details={"status": location.status, "reasons": location.status_reasons},
    )
    db.commit()
    return location


def probe_all(db: Session, settings: Settings) -> dict[str, int]:
    """Sondea todas las ubicaciones y guarda su estado (tarea periódica del worker; sin auditoría por ser del sistema).

    Returns:
        Recuento de ubicaciones por estado.
    """
    counts: dict[str, int] = {}
    for location in db.scalars(select(Location).where(Location.tenant_id == DEFAULT_TENANT_ID)):
        _apply_probe(location, settings)
        counts[location.status] = counts.get(location.status, 0) + 1
        db.commit()
    return counts


def _page(resolved: ResolvedPath, settings: Settings, *, limit: int, offset: int) -> FolderPage:
    names = list_subfolders(resolved, timeout=settings.location_probe_timeout_seconds)
    return FolderPage(
        path=resolved.relative,
        parent=parent_of(resolved.relative),
        names=names[offset : offset + limit],
        total=len(names),
    )


def browse(location: Location, path: str | None, *, settings: Settings, limit: int, offset: int) -> FolderPage:
    """Subcarpetas de ``path`` dentro de ``location``.

    Raises:
        InvalidRelativePathError: Sintaxis no válida (400).
        FolderNotFoundError: No existe o queda fuera de la ubicación (404, sin distinguir).
        LocationUnavailableError: La ubicación está caída o no responde (503).
    """
    if location.status == "unavailable":
        # Un montaje caído puede colgar el primer acceso: se comprueba antes con el timeout del sondeo.
        reachable = run_with_timeout(
            lambda: Path(location.container_path).is_dir(), settings.location_probe_timeout_seconds
        )
        if not reachable:
            raise LocationUnavailableError("La ubicación no está disponible ahora mismo.")
    resolved = resolve_within(Path(location.container_path), path, timeout=settings.location_probe_timeout_seconds)
    return _page(resolved, settings, limit=limit, offset=offset)


def browse_mounts(path: str | None, *, settings: Settings, limit: int, offset: int) -> FolderPage:
    """Subcarpetas bajo ``DOW_LOCATIONS_ROOT`` para elegir la carpeta de una ubicación nueva (solo admin)."""
    resolved = resolve_within(settings.locations_root, path, timeout=settings.location_probe_timeout_seconds)
    return _page(resolved, settings, limit=limit, offset=offset)


def aggregate_status(db: Session) -> str:
    """Estado agregado para ``/api/health``: ``none``, ``ok``, ``degraded`` o ``unavailable`` (el peor)."""
    statuses = set(db.scalars(select(Location.status).where(Location.tenant_id == DEFAULT_TENANT_ID)))
    if not statuses:
        return "none"
    for worst in ("unavailable", "degraded"):
        if worst in statuses:
            return worst
    return "ok"
