"""Casos de uso de proyectos: alta, consulta con control de acceso, edición y miembros.

Acceso (Fase 3, hasta los roles de la Fase 9): un admin de la instancia actúa como ``owner`` en todos los proyectos;
el resto solo ve los proyectos de los que es miembro. Un proyecto ajeno o borrado da 404, nunca 403.

La carpeta de salidas pertenece al proyecto: al crearlo debe ser nueva (la crea la API) o estar vacía, de modo que
vaciar o borrar el proyecto nunca toca ficheros ajenos (decisión del mantenedor, 2026-11-01).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import (
    ACTIVE_RUN_STATUSES,
    DEFAULT_TENANT_ID,
    Location,
    MemberRole,
    Project,
    ProjectMember,
    Run,
    User,
    utcnow,
)
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction, RequestContext
from app.domain.locations.errors import FolderNotFoundError, LocationUnavailableError
from app.domain.locations.paths import (
    ResolvedPath,
    join_relative,
    normalize_relative,
    resolve_within,
    run_with_timeout,
)
from app.domain.locations.service import get_location
from app.domain.projects.errors import (
    FolderNotEmptyError,
    InvalidProjectError,
    MemberConflictError,
    MemberNotFoundError,
    ProjectConflictError,
    ProjectForbiddenError,
    ProjectNotFoundError,
)
from app.domain.projects.folders import folder_name_problem, nested, without_nested

MAX_SOURCE_SUBPATHS: Final = 20
ROLE_RANK: Final[dict[str, int]] = {"viewer": 1, "editor": 2, "owner": 3}


@dataclass(frozen=True)
class ProjectAccess:
    """Proyecto visible y rol efectivo del usuario en él (``owner`` para un admin)."""

    project: Project
    role: MemberRole


def state_dir(settings: Settings, project_id: int) -> Path:
    """Carpeta de estado de doc_organize del proyecto en el volumen local ``data`` (ADR-005), construida con el id."""
    return settings.data_dir / "projects" / str(int(project_id))


# --- acceso ------------------------------------------------------------------------------------------------------


def _member_role(db: Session, project_id: int, user_id: int) -> str | None:
    return db.scalar(
        select(ProjectMember.role).where(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
    )


def get_access(
    db: Session, project_id: int, user: User, *, min_role: MemberRole = "viewer", include_deleted: bool = False
) -> ProjectAccess:
    """Proyecto visible para ``user`` con al menos ``min_role``.

    Raises:
        ProjectNotFoundError: No existe, está borrado (salvo ``include_deleted``) o el usuario no es miembro.
        ProjectForbiddenError: Es miembro, pero con un rol inferior a ``min_role``.
    """
    project = db.get(Project, project_id)
    if project is None or project.tenant_id != DEFAULT_TENANT_ID:
        raise ProjectNotFoundError()
    if project.status == "deleted" and not include_deleted:
        raise ProjectNotFoundError()
    role = "owner" if user.role == "admin" else _member_role(db, project.id, user.id)
    if role is None:
        raise ProjectNotFoundError()
    if ROLE_RANK[role] < ROLE_RANK[min_role]:
        raise ProjectForbiddenError()
    return ProjectAccess(project=project, role=cast(MemberRole, role))


def visible_project_ids(user: User) -> Select[int]:
    """Subconsulta de ids de proyecto visibles para ``user`` (todos para un admin), incluidos los borrados."""
    query = select(Project.id).where(Project.tenant_id == DEFAULT_TENANT_ID)
    if user.role != "admin":
        query = query.where(Project.id.in_(select(ProjectMember.project_id).where(ProjectMember.user_id == user.id)))
    return query


def list_projects(
    db: Session, user: User, *, q: str | None, limit: int, offset: int
) -> tuple[list[ProjectAccess], int]:
    """Proyectos activos visibles para ``user`` ordenados por nombre, con su rol."""
    query = select(Project).where(Project.status == "active", Project.id.in_(visible_project_ids(user)))
    if q:
        query = query.where(func.lower(Project.name).contains(q.strip().lower(), autoescape=True))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(func.lower(Project.name)).limit(limit).offset(offset)).unique().all()
    roles: dict[int, str] = {}
    if user.role != "admin" and rows:
        roles = dict(
            db.execute(
                select(ProjectMember.project_id, ProjectMember.role).where(
                    ProjectMember.user_id == user.id, ProjectMember.project_id.in_([p.id for p in rows])
                )
            ).all()
        )
    return [ProjectAccess(p, cast(MemberRole, "owner" if user.role == "admin" else roles[p.id])) for p in rows], total


def last_runs(db: Session, project_ids: list[int]) -> dict[int, Run]:
    """Último run de cada proyecto de ``project_ids``."""
    if not project_ids:
        return {}
    latest = (
        select(Run.project_id, func.max(Run.created_at).label("ts"))
        .where(Run.project_id.in_(project_ids))
        .group_by(Run.project_id)
        .subquery()
    )
    rows = db.scalars(
        select(Run).join(latest, (Run.project_id == latest.c.project_id) & (Run.created_at == latest.c.ts))
    ).unique()
    return {run.project_id: run for run in rows if run.project_id is not None}


def has_active_run(db: Session, project_id: int) -> bool:
    """Si el proyecto tiene algún run en cola o en marcha."""
    query = select(Run.id).where(Run.project_id == project_id, Run.status.in_(ACTIVE_RUN_STATUSES)).limit(1)
    return db.scalar(query) is not None


# --- validación de ubicaciones y carpetas ----------------------------------------------------------------------


def _check_reachable(location: Location) -> None:
    if location.status == "unavailable":
        raise LocationUnavailableError("La ubicación no está disponible ahora mismo.")


def source_location(db: Session, location_id: int) -> Location:
    """Ubicación de uso ``source`` o ``both``.

    Raises:
        LocationNotFoundError: No existe.
        InvalidProjectError: No es de origen.
    """
    location = get_location(db, location_id)
    if location.usage not in ("source", "both"):
        raise InvalidProjectError("La ubicación de origen no está registrada como origen.")
    return location


def destination_location(db: Session, location_id: int) -> Location:
    """Ubicación de uso ``destination`` o ``both`` con acceso ``rw``.

    Raises:
        LocationNotFoundError: No existe.
        InvalidProjectError: No es de destino o es de solo lectura.
    """
    location = get_location(db, location_id)
    if location.usage not in ("destination", "both"):
        raise InvalidProjectError("La ubicación de destino no está registrada como destino.")
    if location.access != "rw":
        raise InvalidProjectError("La ubicación de destino es de solo lectura.")
    return location


def resolve_sources(location: Location, subpaths: list[str], settings: Settings) -> list[str]:
    """Subcarpetas de origen resueltas dentro de la ubicación, sin repetidas ni contenidas en otra.

    Raises:
        InvalidProjectError: Ninguna o más de ``MAX_SOURCE_SUBPATHS``.
        InvalidRelativePathError, FolderNotFoundError, LocationUnavailableError: Del resolvedor.
    """
    if not subpaths or len(subpaths) > MAX_SOURCE_SUBPATHS:
        raise InvalidProjectError(f"Elige entre 1 y {MAX_SOURCE_SUBPATHS} carpetas de origen.")
    _check_reachable(location)
    root = Path(location.container_path)
    timeout = settings.location_probe_timeout_seconds
    return without_nested([resolve_within(root, sub, timeout=timeout).relative for sub in subpaths])


def _is_empty_dir(path: Path) -> bool:
    with os.scandir(path) as entries:
        return next(entries, None) is None


def prepare_output_folder(
    location: Location, parent: str, new_folder: str | None, settings: Settings
) -> tuple[ResolvedPath, bool]:
    """Carpeta de salidas: ``parent/new_folder`` nueva (se crea) o ``parent`` vacía.

    Returns:
        La carpeta resuelta y si se ha creado ahora (para borrarla si el alta falla después).

    Raises:
        InvalidProjectError: Nombre de carpeta no válido o la raíz de la ubicación como carpeta del proyecto.
        ProjectConflictError: La carpeta nueva ya existe.
        FolderNotEmptyError: La carpeta existente no está vacía.
        InvalidRelativePathError, FolderNotFoundError, LocationUnavailableError: Del resolvedor.
    """
    _check_reachable(location)
    root = Path(location.container_path)
    timeout = settings.location_probe_timeout_seconds
    base = resolve_within(root, parent, timeout=timeout)
    if new_folder is None:
        if not base.relative:
            raise InvalidProjectError("Elige una carpeta dentro de la ubicación, no su raíz.")
        if not run_with_timeout(lambda: _is_empty_dir(base.absolute), timeout):
            raise FolderNotEmptyError("La carpeta de salidas debe estar vacía o ser nueva.")
        return base, False
    problem = folder_name_problem(new_folder)
    if problem:
        raise InvalidProjectError(problem)
    target = base.absolute / new_folder

    def _create() -> bool:
        try:
            target.mkdir()
        except FileExistsError:
            return False
        return True

    try:
        created = run_with_timeout(_create, timeout)
    except OSError as exc:
        raise LocationUnavailableError("No se puede crear la carpeta en la ubicación de destino.") from exc
    if not created:
        raise ProjectConflictError("Ya existe una carpeta con ese nombre en el destino.")
    try:
        resolved = resolve_within(root, join_relative(base.relative, new_folder), timeout=timeout)
    except FolderNotFoundError:
        remove_empty_folder(target)
        raise
    return resolved, True


def remove_empty_folder(path: Path) -> None:
    """Borra ``path`` si está vacía (deshace una carpeta recién creada); ignora errores."""
    try:
        path.rmdir()
    except OSError:
        pass


def check_destination_free(
    db: Session,
    *,
    destination_location_id: int,
    destination_subpath: str,
    source_location_id: int,
    source_subpaths: list[str],
    exclude_project_id: int | None = None,
) -> None:
    """La carpeta de salidas no se solapa con el origen del proyecto ni con las salidas de otro proyecto activo.

    Raises:
        InvalidProjectError: Solape con el origen (el escaneo leería sus propias salidas).
        ProjectConflictError: Solape con otro proyecto.
    """
    if destination_location_id == source_location_id and any(
        nested(destination_subpath, src) for src in source_subpaths
    ):
        raise InvalidProjectError("La carpeta de salidas no puede estar dentro del origen ni contenerlo.")
    query = select(Project.id, Project.destination_subpath).where(
        Project.status == "active", Project.destination_location_id == destination_location_id
    )
    if exclude_project_id is not None:
        query = query.where(Project.id != exclude_project_id)
    for _, other in db.execute(query):
        if nested(destination_subpath, other):
            raise ProjectConflictError("Otro proyecto ya usa esa carpeta de salidas (o una que la contiene).")


def _name_taken(db: Session, name: str, *, exclude_id: int | None = None) -> bool:
    query = select(Project.id).where(
        Project.tenant_id == DEFAULT_TENANT_ID,
        Project.status == "active",
        func.lower(Project.name) == name.strip().lower(),
    )
    if exclude_id is not None:
        query = query.where(Project.id != exclude_id)
    return db.scalar(query) is not None


# --- alta y edición ----------------------------------------------------------------------------------------------


def create_project(
    db: Session,
    *,
    name: str,
    description: str | None,
    source_location_id: int,
    source_subpaths: list[str],
    destination_location_id: int,
    destination_parent: str,
    new_folder: str | None,
    settings: Settings,
    actor: User,
    ctx: RequestContext,
) -> Project:
    """Crea el proyecto con ``actor`` como ``owner``, su carpeta de salidas y su carpeta de estado.

    Raises:
        ProjectConflictError: Nombre repetido, carpeta nueva ya existente o salidas de otro proyecto.
        FolderNotEmptyError: Carpeta existente con contenido.
        InvalidProjectError: Ubicaciones de uso o acceso incorrectos, solapes o nombre de carpeta no válido.
        LocationNotFoundError, InvalidRelativePathError, FolderNotFoundError, LocationUnavailableError: Ubicaciones.
    """
    if _name_taken(db, name):
        raise ProjectConflictError("Ya hay un proyecto con ese nombre.")
    source = source_location(db, source_location_id)
    destination = destination_location(db, destination_location_id)
    sources = resolve_sources(source, source_subpaths, settings)
    parent = normalize_relative(destination_parent)
    planned = join_relative(parent, new_folder) if new_folder else parent
    check_destination_free(
        db,
        destination_location_id=destination.id,
        destination_subpath=planned,
        source_location_id=source.id,
        source_subpaths=sources,
    )
    output, created = prepare_output_folder(destination, destination_parent, new_folder, settings)
    try:
        project = Project(
            name=name.strip(),
            description=(description or "").strip() or None,
            source_location_id=source.id,
            source_subpaths=sources,
            destination_location_id=destination.id,
            destination_subpath=output.relative,
            created_by=actor.id,
        )
        db.add(project)
        db.flush()
        db.add(ProjectMember(project_id=project.id, user_id=actor.id, role="owner", added_by=actor.id))
        state_dir(settings, project.id).mkdir(parents=True, exist_ok=True)
        audit.record(
            db,
            action=AuditAction.PROJECT_CREATE,
            ctx=ctx,
            actor_id=actor.id,
            target_type="project",
            target_id=project.id,
            details={
                "name": project.name,
                "source_location_id": source.id,
                "source_subpaths": sources,
                "destination_location_id": destination.id,
                "destination_subpath": output.relative,
                "new_folder": created,
            },
        )
        db.commit()
    except Exception:
        db.rollback()
        if created:
            remove_empty_folder(output.absolute)
        raise
    return project


@dataclass(frozen=True)
class ProjectChanges:
    """Cambios de un ``PATCH``; ``None`` = sin cambio. Origen y destino solo cambian con runs (mover) o aquí."""

    name: str | None = None
    description: str | None = None
    source_subpaths: list[str] | None = None


def update_project(
    db: Session, access: ProjectAccess, changes: ProjectChanges, *, settings: Settings, actor: User, ctx: RequestContext
) -> Project:
    """Renombra (solo en la BD), cambia la descripción o las carpetas de origen.

    Raises:
        ProjectConflictError: Nombre repetido, o cambio de origen con un run en marcha.
        InvalidProjectError: Origen solapado con las salidas.
    """
    project = access.project
    changed: list[str] = []
    if changes.name is not None and changes.name.strip() != project.name:
        if _name_taken(db, changes.name, exclude_id=project.id):
            raise ProjectConflictError("Ya hay un proyecto con ese nombre.")
        project.name = changes.name.strip()
        changed.append("name")
    if changes.description is not None and (changes.description.strip() or None) != project.description:
        project.description = changes.description.strip() or None
        changed.append("description")
    if changes.source_subpaths is not None:
        sources = resolve_sources(project.source_location, changes.source_subpaths, settings)
        if sources != project.source_subpaths:
            if has_active_run(db, project.id):
                raise ProjectConflictError("No se puede cambiar el origen con una ejecución en marcha.")
            check_destination_free(
                db,
                destination_location_id=project.destination_location_id,
                destination_subpath=project.destination_subpath,
                source_location_id=project.source_location_id,
                source_subpaths=sources,
                exclude_project_id=project.id,
            )
            project.source_subpaths = sources
            changed.append("source_subpaths")
    if changed:
        project.updated_at = utcnow()
        audit.record(
            db,
            action=AuditAction.PROJECT_UPDATE,
            ctx=ctx,
            actor_id=actor.id,
            target_type="project",
            target_id=project.id,
            details={"fields": changed},
        )
    db.commit()
    return project


# --- miembros ----------------------------------------------------------------------------------------------------


def list_members(db: Session, project: Project) -> list[ProjectMember]:
    """Miembros ordenados por rol (owner primero) y nombre de usuario."""
    rows = db.scalars(select(ProjectMember).where(ProjectMember.project_id == project.id)).unique().all()
    return sorted(rows, key=lambda m: (-ROLE_RANK[m.role], m.user.username))


def _owners(db: Session, project_id: int) -> int:
    query = select(func.count()).where(ProjectMember.project_id == project_id, ProjectMember.role == "owner")
    return db.scalar(query) or 0


def add_member(
    db: Session, project: Project, *, user_id: int, role: MemberRole, actor: User, ctx: RequestContext
) -> ProjectMember:
    """Añade un usuario activo como miembro.

    Raises:
        MemberNotFoundError: El usuario no existe o está desactivado.
        MemberConflictError: Ya es miembro.
    """
    target = db.get(User, user_id)
    if target is None or not target.is_active or target.tenant_id != project.tenant_id:
        raise MemberNotFoundError("El usuario no existe o está desactivado.")
    if _member_role(db, project.id, user_id) is not None:
        raise MemberConflictError("El usuario ya es miembro del proyecto.")
    member = ProjectMember(project_id=project.id, user_id=user_id, role=role, added_by=actor.id)
    db.add(member)
    audit.record(
        db,
        action=AuditAction.PROJECT_MEMBER_ADD,
        ctx=ctx,
        actor_id=actor.id,
        target_type="project",
        target_id=project.id,
        details={"user_id": user_id, "role": role},
    )
    db.commit()
    db.refresh(member)
    return member


def _get_member(db: Session, project: Project, user_id: int) -> ProjectMember:
    member = db.get(ProjectMember, (project.id, user_id))
    if member is None:
        raise MemberNotFoundError()
    return member


def update_member(
    db: Session, project: Project, *, user_id: int, role: MemberRole, actor: User, ctx: RequestContext
) -> ProjectMember:
    """Cambia el rol de un miembro.

    Raises:
        MemberNotFoundError: No es miembro.
        MemberConflictError: Dejaría el proyecto sin ``owner``.
    """
    member = _get_member(db, project, user_id)
    if member.role == role:
        return member
    if member.role == "owner" and _owners(db, project.id) <= 1:
        raise MemberConflictError("El proyecto debe tener al menos un propietario.")
    previous = member.role
    member.role = role
    audit.record(
        db,
        action=AuditAction.PROJECT_MEMBER_UPDATE,
        ctx=ctx,
        actor_id=actor.id,
        target_type="project",
        target_id=project.id,
        details={"user_id": user_id, "from": previous, "to": role},
    )
    db.commit()
    return member


def remove_member(db: Session, project: Project, *, user_id: int, actor: User, ctx: RequestContext) -> None:
    """Quita un miembro.

    Raises:
        MemberNotFoundError: No es miembro.
        MemberConflictError: Es el último ``owner``.
    """
    member = _get_member(db, project, user_id)
    if member.role == "owner" and _owners(db, project.id) <= 1:
        raise MemberConflictError("El proyecto debe tener al menos un propietario.")
    db.delete(member)
    audit.record(
        db,
        action=AuditAction.PROJECT_MEMBER_REMOVE,
        ctx=ctx,
        actor_id=actor.id,
        target_type="project",
        target_id=project.id,
        details={"user_id": user_id},
    )
    db.commit()


def projects_using_location(db: Session, location_id: int) -> int:
    """Proyectos (incluidos los borrados, que conservan su historial) que usan la ubicación."""
    query = select(func.count()).where(
        or_(Project.source_location_id == location_id, Project.destination_location_id == location_id)
    )
    return db.scalar(query) or 0
