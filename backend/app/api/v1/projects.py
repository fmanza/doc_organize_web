"""``/api/v1/projects``: proyectos, miembros y lanzamiento de ejecuciones (Fase 3); carpetas guardadas y errores de
escaneo (Fase 4).

Un proyecto ajeno (o borrado) da 404; un miembro con rol insuficiente, 403. Las respuestas nunca llevan rutas del
contenedor: solo el nombre de las ubicaciones y rutas relativas a ellas.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, Query, status

from app.api.deps import Context, CurrentUser, DbSession, SettingsDep
from app.api.v1.fs import FS_ERRORS
from app.api.v1.runs import run_out
from app.api.v1.schemas import (
    MAX_PAGE_SIZE,
    LocationRef,
    MemberCreate,
    MemberList,
    MemberOut,
    MemberUpdate,
    ProjectCreate,
    ProjectOut,
    ProjectPage,
    ProjectUpdate,
    RunBrief,
    RunOut,
    ScanErrorOut,
    ScanErrorPage,
    ScannedFolderCreate,
    ScannedFolderList,
    ScannedFolderOut,
    ScannedFolderRemoved,
)
from app.db.models import ProjectMember, Run
from app.domain.projects import service
from app.domain.projects.service import ProjectAccess, ProjectChanges
from app.domain.runs import service as runs
from app.domain.runs.operations import RunParams
from app.domain.scan import folders as scan_folders
from app.domain.scan import scan_errors
from app.domain.scan.folders import FolderStatus

router = APIRouter(prefix="/projects", tags=["projects"])

_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"description": "No autenticado"},
    403: {"description": "Rol insuficiente en el proyecto o token CSRF no válido"},
    404: {"description": "Proyecto no encontrado (o sin acceso)"},
}


def project_out(access: ProjectAccess, last_run: Run | None = None, *, active_run: bool = False) -> ProjectOut:
    """Respuesta HTTP de un proyecto."""
    p = access.project
    return ProjectOut(
        id=p.id,
        name=p.name,
        description=p.description,
        source_location=LocationRef.model_validate(p.source_location),
        source_subpaths=p.source_subpaths,
        destination_location=LocationRef.model_validate(p.destination_location),
        destination_subpath=p.destination_subpath,
        role=access.role,
        created_at=p.created_at,
        updated_at=p.updated_at,
        last_run=RunBrief.model_validate(last_run) if last_run else None,
        active_run=active_run,
    )


def _member_out(member: ProjectMember) -> MemberOut:
    return MemberOut(
        user_id=member.user_id,
        username=member.user.username,
        display_name=member.user.display_name,
        role=member.role,
        added_at=member.added_at,
    )


@router.get("", response_model=ProjectPage, summary="Listar proyectos", responses={401: _ERRORS[401]})
def list_projects(
    user: CurrentUser,
    db: DbSession,
    q: Annotated[str | None, Query(max_length=128, description="Texto en el nombre")] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ProjectPage:
    """Proyectos de los que el usuario es miembro (un admin ve todos), con su rol y el último run."""
    rows, total = service.list_projects(db, user, q=q, limit=limit, offset=offset)
    latest = service.last_runs(db, [a.project.id for a in rows])
    return ProjectPage(items=[project_out(a, latest.get(a.project.id)) for a in rows], total=total)


@router.post(
    "",
    response_model=ProjectOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear proyecto",
    responses={
        **FS_ERRORS,
        409: {"description": "Nombre repetido, carpeta existente o no vacía, o salidas de otro proyecto"},
    },
)
def create_project(
    body: ProjectCreate, user: CurrentUser, db: DbSession, settings: SettingsDep, ctx: Context
) -> ProjectOut:
    """Crea el proyecto (el usuario queda como ``owner``) y su carpeta de salidas si es nueva."""
    project = service.create_project(
        db,
        name=body.name,
        description=body.description,
        source_location_id=body.source_location_id,
        source_subpaths=body.source_subpaths,
        destination_location_id=body.destination_location_id,
        destination_parent=body.destination_parent,
        new_folder=body.new_folder,
        settings=settings,
        actor=user,
        ctx=ctx,
    )
    return project_out(ProjectAccess(project, "owner"))


@router.get("/{project_id}", response_model=ProjectOut, summary="Ver proyecto", responses=_ERRORS)
def get_project(project_id: int, user: CurrentUser, db: DbSession) -> ProjectOut:
    """Detalle del proyecto con su último run."""
    access = service.get_access(db, project_id, user)
    latest = service.last_runs(db, [project_id]).get(project_id)
    return project_out(access, latest, active_run=service.has_active_run(db, project_id))


@router.patch(
    "/{project_id}",
    response_model=ProjectOut,
    summary="Editar proyecto",
    responses={**_ERRORS, **FS_ERRORS, 409: {"description": "Nombre repetido o run en marcha"}},
)
def update_project(
    project_id: int, body: ProjectUpdate, user: CurrentUser, db: DbSession, settings: SettingsDep, ctx: Context
) -> ProjectOut:
    """Renombra (solo en la BD), cambia la descripción o las carpetas de origen (``owner``)."""
    access = service.get_access(db, project_id, user, min_role="owner")
    changes = ProjectChanges(**body.model_dump(exclude_unset=True))
    service.update_project(db, access, changes, settings=settings, actor=user, ctx=ctx)
    return get_project(project_id, user, db)


# --- miembros ----------------------------------------------------------------------------------------------------


@router.get("/{project_id}/members", response_model=MemberList, summary="Ver miembros", responses=_ERRORS)
def list_members(project_id: int, user: CurrentUser, db: DbSession) -> MemberList:
    """Miembros del proyecto con su rol."""
    access = service.get_access(db, project_id, user)
    return MemberList(items=[_member_out(m) for m in service.list_members(db, access.project)])


@router.post(
    "/{project_id}/members",
    response_model=MemberOut,
    status_code=status.HTTP_201_CREATED,
    summary="Añadir miembro",
    responses={**_ERRORS, 409: {"description": "Ya es miembro"}},
)
def add_member(project_id: int, body: MemberCreate, user: CurrentUser, db: DbSession, ctx: Context) -> MemberOut:
    """Añade un usuario activo con un rol (``owner``)."""
    access = service.get_access(db, project_id, user, min_role="owner")
    member = service.add_member(db, access.project, user_id=body.user_id, role=body.role, actor=user, ctx=ctx)
    return _member_out(member)


@router.patch(
    "/{project_id}/members/{user_id}",
    response_model=MemberOut,
    summary="Cambiar rol de un miembro",
    responses={**_ERRORS, 409: {"description": "Dejaría el proyecto sin propietario"}},
)
def update_member(
    project_id: int, user_id: int, body: MemberUpdate, user: CurrentUser, db: DbSession, ctx: Context
) -> MemberOut:
    """Cambia el rol (``owner``); el proyecto conserva siempre al menos un propietario."""
    access = service.get_access(db, project_id, user, min_role="owner")
    member = service.update_member(db, access.project, user_id=user_id, role=body.role, actor=user, ctx=ctx)
    return _member_out(member)


@router.delete(
    "/{project_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Quitar miembro",
    responses={**_ERRORS, 409: {"description": "Es el último propietario"}},
)
def remove_member(project_id: int, user_id: int, user: CurrentUser, db: DbSession, ctx: Context) -> None:
    """Quita un miembro (``owner``)."""
    access = service.get_access(db, project_id, user, min_role="owner")
    service.remove_member(db, access.project, user_id=user_id, actor=user, ctx=ctx)


# --- carpetas guardadas y errores de escaneo (Fase 4) ---------------------------------------------------------


def _folder_out(status: FolderStatus) -> ScannedFolderOut:
    folder = status.folder
    return ScannedFolderOut(
        subpath=folder.subpath,
        used=folder.used,
        added_at=folder.added_at,
        last_scanned_at=folder.last_scanned_at,
        last_run_id=folder.last_run_id,
        available=status.available,
    )


@router.get(
    "/{project_id}/scanned-folders",
    response_model=ScannedFolderList,
    summary="Ver carpetas de origen",
    responses=_ERRORS,
)
def list_scanned_folders(project_id: int, user: CurrentUser, db: DbSession, settings: SettingsDep) -> ScannedFolderList:
    """Carpetas de origen con su estado en los escaneos y si existen ahora en el origen."""
    access = service.get_access(db, project_id, user)
    statuses = scan_folders.list_folders(db, access.project, settings)
    return ScannedFolderList(
        location=LocationRef.model_validate(access.project.source_location),
        items=[_folder_out(s) for s in statuses],
    )


@router.post(
    "/{project_id}/scanned-folders",
    response_model=ScannedFolderOut,
    status_code=status.HTTP_201_CREATED,
    summary="Añadir carpeta de origen",
    responses={
        **_ERRORS,
        **FS_ERRORS,
        409: {"description": "Ya guardada, solapada con salidas o con ejecuciones en marcha"},
        422: {"description": "Anidada con otra carpeta (nested_folders)"},
    },
)
def add_scanned_folder(
    project_id: int, body: ScannedFolderCreate, user: CurrentUser, db: DbSession, settings: SettingsDep, ctx: Context
) -> ScannedFolderOut:
    """Añade una carpeta de la ubicación de origen (``owner``); no puede estar dentro de otra ni contenerla."""
    access = service.get_access(db, project_id, user, min_role="owner")
    folder = scan_folders.add_folder(db, access, body.subpath, settings=settings, actor=user, ctx=ctx)
    return ScannedFolderOut(
        subpath=folder.subpath,
        used=folder.used,
        added_at=folder.added_at,
        last_scanned_at=folder.last_scanned_at,
        last_run_id=folder.last_run_id,
        available=True,
    )


@router.delete(
    "/{project_id}/scanned-folders",
    response_model=ScannedFolderRemoved,
    summary="Quitar carpeta de origen",
    responses={**_ERRORS, 409: {"description": "Única carpeta (last_folder) o ejecuciones en marcha"}},
)
def remove_scanned_folder(
    project_id: int,
    user: CurrentUser,
    db: DbSession,
    ctx: Context,
    subpath: Annotated[str, Query(max_length=4096, description="Carpeta relativa a la ubicación de origen")],
) -> ScannedFolderRemoved:
    """Quita una carpeta de origen (``owner``). No borra ficheros: si ya se escaneó, sus salidas siguen en el destino."""
    access = service.get_access(db, project_id, user, min_role="owner")
    used = scan_folders.remove_folder(db, access, subpath, actor=user, ctx=ctx)
    return ScannedFolderRemoved(subpath=subpath, used=used)


@router.get(
    "/{project_id}/scan-errors",
    response_model=ScanErrorPage,
    summary="Errores del último escaneo",
    responses=_ERRORS,
)
def list_project_scan_errors(
    project_id: int,
    user: CurrentUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ScanErrorPage:
    """Documentos que no se pudieron convertir en el último escaneo terminado del proyecto."""
    service.get_access(db, project_id, user)
    run = scan_errors.last_scan(db, project_id)
    if run is None:
        return ScanErrorPage(run=None, items=[], total=0)
    rows, total = scan_errors.run_errors(db, run.id, limit=limit, offset=offset)
    return ScanErrorPage(
        run=RunBrief.model_validate(run), items=[ScanErrorOut.model_validate(r) for r in rows], total=total
    )


# --- ejecuciones -------------------------------------------------------------------------------------------------


@router.post(
    "/{project_id}/runs",
    response_model=RunOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Lanzar ejecución",
    responses={
        **_ERRORS,
        400: {"description": "Destino de un movimiento no válido"},
        409: {"description": "Escritura en curso (write_locked), vista previa necesaria (preview_required) o cuota"},
        422: {"description": "Escaneo no válido (option_unavailable, folder_not_saved, force_requires_all_folders)"},
        503: {"description": "Ubicación no disponible"},
    },
)
def enqueue_run(
    project_id: int,
    body: Annotated[RunParams, Body()],
    user: CurrentUser,
    db: DbSession,
    settings: SettingsDep,
    ctx: Context,
) -> RunOut:
    """Encola una operación del proyecto; el worker la ejecuta y el progreso se sigue por SSE."""
    access = service.get_access(db, project_id, user)
    run = runs.enqueue(db, access, body, settings=settings, actor=user, ctx=ctx)
    return run_out(db, run, user, access.role)
