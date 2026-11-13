"""Casos de uso de ubicaciones: registro, edición, borrado, sondeo y explorador de carpetas (ADR-007)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import (
    Location,
    LocationAccess,
    LocationKind,
    LocationUsage,
    User,
    utcnow,
)
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction, RequestContext
from app.domain.listing import ListQuery, apply_search, apply_sort
from app.domain.locations.errors import (
    FolderNotFoundError,
    InvalidIgnorePatternsError,
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
from app.domain.tenancy.tenants import get_tenant


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
    tenant_id: int | None = None
    ignore_patterns: list[str] | None = None


#: Patrones de nombre por ubicación de origen (1.4.0, G41): cuántos y de qué longitud como mucho.
MAX_IGNORE_PATTERNS = 30
MAX_IGNORE_PATTERN_LENGTH = 64


def check_ignore_patterns(patterns: list[str]) -> list[str]:
    """Valida los patrones ``fnmatch`` de nombre de una ubicación y los devuelve sin repetidos, en su orden.

    Raises:
        InvalidIgnorePatternsError: Más de ``MAX_IGNORE_PATTERNS``, alguno vacío, con separadores o demasiado largo.
    """
    if len(patterns) > MAX_IGNORE_PATTERNS:
        raise InvalidIgnorePatternsError(f"Se admiten como mucho {MAX_IGNORE_PATTERNS} patrones.")
    for pattern in patterns:
        if not pattern.strip():
            raise InvalidIgnorePatternsError("Hay un patrón vacío.")
        if "/" in pattern or "\\" in pattern:
            raise InvalidIgnorePatternsError(f"«{pattern}» lleva «/» o «\\»: los patrones son de nombre, no de ruta.")
        if len(pattern) > MAX_IGNORE_PATTERN_LENGTH:
            raise InvalidIgnorePatternsError(
                f"«{pattern[:MAX_IGNORE_PATTERN_LENGTH]}…» supera los {MAX_IGNORE_PATTERN_LENGTH} caracteres."
            )
    return list(dict.fromkeys(patterns))


def list_locations(
    db: Session, *, tenant_id: int, limit: int, offset: int, listing: ListQuery | None = None
) -> tuple[list[Location], int]:
    """Ubicaciones del tenant (por nombre si no se pide otro orden; Fase 9: cada una es de un tenant), filtradas por
    texto en el nombre o la ruta visible."""
    listing = listing or ListQuery()
    query = select(Location).where(Location.tenant_id == tenant_id)
    query = apply_search(query, listing.q, [Location.name, Location.display_path])
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    columns = {
        "name": func.lower(Location.name),
        "usage": Location.usage,
        "access": Location.access,
        "status": Location.status,
        "probed_at": Location.probed_at,
    }
    query = apply_sort(query, listing, columns, default=[func.lower(Location.name)], tiebreak=Location.id)
    rows = db.scalars(query.limit(limit).offset(offset)).all()
    return list(rows), total


def get_location(db: Session, location_id: int, *, tenant_id: int) -> Location:
    """Ubicación del tenant por id (autorización antes que existencia, regla 5).

    Raises:
        LocationNotFoundError: No existe o es de otro tenant (no se revela cuál).
    """
    location = db.get(Location, location_id)
    if location is None or location.tenant_id != tenant_id:
        raise LocationNotFoundError()
    return location


def _validate_container_path(
    db: Session, relative_to_root: str, settings: Settings, *, tenant_id: int, usage: LocationUsage
) -> Path:
    """Carpeta bajo ``DOW_LOCATIONS_ROOT`` para una ubicación nueva de ``tenant_id``, resuelta y sin solapes.

    Los errores de solape dicen con qué ubicación choca la carpeta y cómo (1.4.4); de las de otro tenant no dan el
    nombre. Nunca incluyen la ruta del contenedor.

    Raises:
        InvalidLocationPathError: Fuera de la raíz, inexistente, la propia raíz, dentro de ``data``/``workspace`` o
            solapada con otra ubicación.
        LocationConflictError: Otra ubicación ya usa esa misma carpeta.
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
    contained: list[str] = []
    contained_elsewhere = 0
    for other_path_text, other_tenant, other_name, other_usage in db.execute(
        select(Location.container_path, Location.tenant_id, Location.name, Location.usage)
    ):
        other_path = Path(other_path_text)
        own = other_tenant == tenant_id
        if path == other_path:
            raise LocationConflictError(
                f"Ya hay una ubicación con esa carpeta: «{other_name}»."
                if own
                else "La carpeta ya está registrada en otro tenant."
            )
        if path.is_relative_to(other_path):
            # Las ubicaciones registradas no se solapan entre sí: la carpeta solo puede estar dentro de una.
            raise InvalidLocationPathError(
                _inside_message(other_name, other_usage, usage, path.relative_to(other_path).as_posix())
                if own
                else "La carpeta está dentro de una ubicación de otro tenant."
            )
        if other_path.is_relative_to(path):
            if own:
                contained.append(other_name)
            else:
                contained_elsewhere += 1
    if contained or contained_elsewhere:
        raise InvalidLocationPathError(_contains_message(sorted(contained, key=str.lower), contained_elsewhere))
    return path


_MAX_NAMED_LOCATIONS = 3


def _inside_message(other_name: str, other_usage: str, usage: LocationUsage, subpath: str) -> str:
    """Error de una carpeta dentro de la ubicación ``other_name`` del mismo tenant; si las dos son de destino,
    sugiere usar esa ubicación con ``subpath`` como carpeta de salidas del proyecto."""
    message = f"La carpeta está dentro de la ubicación «{other_name}»."
    if other_usage != "source" and usage != "source":
        message += (
            f" Para escribir ahí, usa «{other_name}» como destino del proyecto con la carpeta de salidas «{subpath}»."
        )
    return message


def _contains_message(names: list[str], elsewhere: int) -> str:
    """Error de una carpeta que contiene las ubicaciones ``names`` del tenant y ``elsewhere`` de otros tenants (de
    estas solo se da el número)."""
    if not names:
        return (
            "La carpeta contiene una ubicación de otro tenant."
            if elsewhere == 1
            else f"La carpeta contiene {elsewhere} ubicaciones de otros tenants."
        )
    shown = [f"«{name}»" for name in names[:_MAX_NAMED_LOCATIONS]]
    rest = [f"{len(names) - len(shown)} más"] if len(names) > len(shown) else []
    if elsewhere:
        rest.append(f"{elsewhere} de otro tenant" if elsewhere == 1 else f"{elsewhere} de otros tenants")
    items = shown + rest
    listed = items[0] if len(items) == 1 else f"{', '.join(items[:-1])} y {items[-1]}"
    noun = "la ubicación" if len(names) == 1 and not elsewhere else "las ubicaciones"
    return f"La carpeta contiene {noun} {listed}."


def _name_taken(db: Session, tenant_id: int, name: str, *, exclude_id: int | None = None) -> bool:
    query = select(Location.id).where(
        Location.tenant_id == tenant_id, func.lower(Location.name) == name.strip().lower()
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
    tenant_id: int,
    ignore_patterns: list[str] | None = None,
) -> Location:
    """Registra una ubicación del tenant con la carpeta ``path`` (relativa a ``DOW_LOCATIONS_ROOT``) y la sondea.

    Una carpeta pertenece a una sola ubicación, y por tanto a un solo tenant (no se solapan). ``ignore_patterns``
    (1.4.1): patrones de nombre que no se escanean, solo en ubicaciones de origen.

    Raises:
        LocationConflictError: Nombre o carpeta ya registrados.
        InvalidLocationPathError: Carpeta no válida.
        InvalidIgnorePatternsError: Patrones no válidos, o en una ubicación de destino.
    """
    patterns = check_ignore_patterns(ignore_patterns or [])
    if patterns and usage == "destination":
        raise InvalidIgnorePatternsError("Los patrones solo se aplican a ubicaciones de origen.")
    if _name_taken(db, tenant_id, name):
        raise LocationConflictError("Ya hay una ubicación con ese nombre.")
    container_path = _validate_container_path(db, path, settings, tenant_id=tenant_id, usage=usage)
    location = Location(
        tenant_id=tenant_id,
        name=name.strip(),
        container_path=str(container_path),
        display_path=(display_path or "").strip() or None,
        kind=kind,
        usage=usage,
        access=access,
        ignore_patterns=patterns,
    )
    _apply_probe(location, settings)
    db.add(location)
    db.flush()
    details: dict[str, object] = {"name": location.name, "usage": usage, "access": access, "status": location.status}
    if patterns:
        details["ignore_patterns"] = patterns
    audit.record(
        db,
        action=AuditAction.LOCATION_CREATE,
        ctx=ctx,
        actor_id=actor.id,
        target_type="location",
        target_id=location.id,
        details=details,
    )
    db.commit()
    return location


def update_location(
    db: Session, location: Location, changes: LocationChanges, *, settings: Settings, actor: User, ctx: RequestContext
) -> Location:
    """Aplica ``changes``; si cambia el acceso, vuelve a sondear. ``tenant_id`` la pasa a otro tenant (solo si ningún
    proyecto la usa: un proyecto solo usa ubicaciones de su tenant).

    Raises:
        LocationConflictError: El nombre nuevo ya existe, o se cambia de tenant y algún proyecto la usa.
        TenantNotFoundError: El tenant nuevo no existe.
    """
    changed: list[str] = []
    if changes.tenant_id is not None and changes.tenant_id != location.tenant_id:
        from app.domain.projects.service import projects_using_location

        get_tenant(db, changes.tenant_id)
        if projects_using_location(db, location.id):
            raise LocationConflictError("Algún proyecto usa la ubicación: no puede cambiar de tenant.")
        if _name_taken(db, changes.tenant_id, location.name):
            raise LocationConflictError("El otro tenant ya tiene una ubicación con ese nombre.")
        location.tenant_id = changes.tenant_id
        changed.append("tenant_id")
    if changes.name is not None and changes.name.strip() != location.name:
        if _name_taken(db, location.tenant_id, changes.name, exclude_id=location.id):
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
    details: dict[str, object] = {}
    if changes.ignore_patterns is not None:
        patterns = check_ignore_patterns(changes.ignore_patterns)
        if patterns and location.usage == "destination":
            raise InvalidIgnorePatternsError("Los patrones solo se aplican a ubicaciones de origen.")
        before = list(location.ignore_patterns or [])
        if patterns != before:
            location.ignore_patterns = patterns
            changed.append("ignore_patterns")
            details["ignore_patterns"] = {"before": before, "after": patterns}
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
            details={"fields": changed, **details},
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
    for location in db.scalars(select(Location)):  # todas: el sondeo es de la instancia
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
    statuses = set(db.scalars(select(Location.status)))  # /api/health: estado de la instancia
    if not statuses:
        return "none"
    for worst in ("unavailable", "degraded"):
        if worst in statuses:
            return worst
    return "ok"
