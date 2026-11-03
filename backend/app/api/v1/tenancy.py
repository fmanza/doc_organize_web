"""Tenants (admin de instancia) y roles con permisos del tenant activo (``roles.manage``), Fase 9 (ADR-013).

Paridad con ``tenants.py`` y ``admin.py`` (roles) de la web integrada. Los usuarios de un tenant se gestionan con
``/users`` (el admin de instancia indica ``tenant_id``); ``/tenants/{id}/users`` los lista.
"""

from __future__ import annotations

from typing import Annotated, Any, cast

from fastapi import APIRouter, Query, status
from sqlalchemy.orm import Session

from app.api.deps import Context, DbSession, InstanceAdmin, RoleManager, RoleReader
from app.api.v1.schemas import (
    MAX_PAGE_SIZE,
    Permission,
    PermissionList,
    RoleCreate,
    RoleList,
    RoleOut,
    RoleUpdate,
    TenantCreate,
    TenantOut,
    TenantPage,
    TenantUpdate,
    UserOut,
    UserPage,
)
from app.db.models import TenantRole
from app.domain.identity import users
from app.domain.tenancy import roles, tenants
from app.domain.tenancy.permissions import PERMISSIONS
from app.domain.tenancy.tenants import TenantView

router = APIRouter(tags=["tenancy"])

_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"description": "No autenticado"},
    403: {"description": "Sin permiso o token CSRF no válido"},
}
_404: dict[int | str, dict[str, Any]] = {404: {"description": "No existe (o es de otro tenant)"}}


def _tenant_out(item: TenantView) -> TenantOut:
    tenant = item.tenant
    return TenantOut(
        id=tenant.id,
        slug=tenant.slug,
        name=tenant.name,
        created_at=tenant.created_at,
        users=item.users,
        projects=item.projects,
        locations=item.locations,
        empty=item.empty,
    )


@router.get("/tenants", response_model=TenantPage, summary="Listar tenants", responses=_ERRORS)
def list_tenants(
    _: InstanceAdmin,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TenantPage:
    """Tenants por nombre con sus usuarios, proyectos y ubicaciones."""
    rows, total = tenants.list_tenants(db, limit=limit, offset=offset)
    return TenantPage(items=[_tenant_out(r) for r in rows], total=total)


@router.post(
    "/tenants",
    response_model=TenantOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear tenant",
    responses={**_ERRORS, 409: {"description": "Identificador en uso"}},
)
def create_tenant(body: TenantCreate, admin: InstanceAdmin, db: DbSession, ctx: Context) -> TenantOut:
    """Crea el tenant con sus roles base («Administrador» y «Usuario»)."""
    tenant = tenants.create_tenant(db, slug=body.slug, name=body.name, actor=admin, ctx=ctx)
    return _tenant_out(tenants.view(db, tenant))


@router.patch(
    "/tenants/{tenant_id}",
    response_model=TenantOut,
    summary="Renombrar tenant",
    responses={**_ERRORS, **_404},
)
def update_tenant(tenant_id: int, body: TenantUpdate, admin: InstanceAdmin, db: DbSession, ctx: Context) -> TenantOut:
    tenant = tenants.rename_tenant(db, tenants.get_tenant(db, tenant_id), name=body.name, actor=admin, ctx=ctx)
    return _tenant_out(tenants.view(db, tenant))


@router.delete(
    "/tenants/{tenant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Borrar tenant vacío",
    responses={**_ERRORS, **_404, 409: {"description": "No está vacío o es default"}},
)
def delete_tenant(tenant_id: int, admin: InstanceAdmin, db: DbSession, ctx: Context) -> None:
    """Solo sin usuarios, proyectos, ubicaciones ni plantillas (decisión E3)."""
    tenants.delete_tenant(db, tenants.get_tenant(db, tenant_id), actor=admin, ctx=ctx)


@router.get(
    "/tenants/{tenant_id}/users",
    response_model=UserPage,
    summary="Usuarios de un tenant",
    responses={**_ERRORS, **_404},
)
def list_tenant_users(
    tenant_id: int,
    _: InstanceAdmin,
    db: DbSession,
    q: Annotated[str | None, Query(max_length=64)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> UserPage:
    tenants.get_tenant(db, tenant_id)
    rows, total = users.list_users(db, tenant_id=tenant_id, q=q, limit=limit, offset=offset)
    return UserPage(items=[UserOut.model_validate(u) for u in rows], total=total)


# --- roles -------------------------------------------------------------------------------------------------------------


def _role_out(role: TenantRole, count: int) -> RoleOut:
    return RoleOut(
        id=role.id,
        name=role.name,
        builtin=cast(Any, role.builtin),
        permissions=cast(list[Permission], list(role.permissions or [])),
        users=count,
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


def _with_count(db: Session, role: TenantRole) -> RoleOut:
    counts = {view.role.id: view.users for view in roles.list_roles(db, tenant_id=role.tenant_id)}
    return _role_out(role, counts.get(role.id, 0))


@router.get("/permissions", response_model=PermissionList, summary="Catálogo de permisos", responses=_ERRORS)
def list_permissions(_: RoleManager) -> PermissionList:
    return PermissionList(items=list(PERMISSIONS))


@router.get("/roles", response_model=RoleList, summary="Roles del tenant", responses=_ERRORS)
def list_roles(manager: RoleReader, db: DbSession) -> RoleList:
    """Roles del tenant activo con su número de usuarios; los base primero (``roles.manage`` o ``users.manage``)."""
    views = roles.list_roles(db, tenant_id=manager.scope_tenant_id)
    return RoleList(items=[_role_out(v.role, v.users) for v in views])


@router.post(
    "/roles",
    response_model=RoleOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear rol",
    responses={**_ERRORS, 409: {"description": "Nombre en uso"}, 422: {"description": "Permiso desconocido"}},
)
def create_role(body: RoleCreate, manager: RoleManager, db: DbSession, ctx: Context) -> RoleOut:
    """Nadie da un permiso que no tiene (403 ``permission_escalation``)."""
    role = roles.create_role(
        db, tenant_id=manager.scope_tenant_id, name=body.name, permissions=body.permissions, actor=manager, ctx=ctx
    )
    return _role_out(role, 0)


@router.get("/roles/{role_id}", response_model=RoleOut, summary="Ver rol", responses={**_ERRORS, **_404})
def get_role(role_id: int, manager: RoleManager, db: DbSession) -> RoleOut:
    return _with_count(db, roles.get_role(db, role_id, tenant_id=manager.scope_tenant_id))


@router.patch(
    "/roles/{role_id}",
    response_model=RoleOut,
    summary="Editar rol",
    responses={**_ERRORS, **_404, 409: {"description": "Rol base o nombre en uso"}},
)
def update_role(role_id: int, body: RoleUpdate, manager: RoleManager, db: DbSession, ctx: Context) -> RoleOut:
    """Quitar permisos cierra las sesiones de quienes tienen el rol."""
    role = roles.get_role(db, role_id, tenant_id=manager.scope_tenant_id)
    updated = roles.update_role(db, role, name=body.name, permissions=body.permissions, actor=manager, ctx=ctx)
    return _with_count(db, updated)


@router.delete(
    "/roles/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Borrar rol",
    responses={**_ERRORS, **_404, 409: {"description": "Rol base o en uso"}},
)
def delete_role(role_id: int, manager: RoleManager, db: DbSession, ctx: Context) -> None:
    roles.delete_role(db, roles.get_role(db, role_id, tenant_id=manager.scope_tenant_id), actor=manager, ctx=ctx)
