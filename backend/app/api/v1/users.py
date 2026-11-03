"""``/api/v1/users``: usuarios del tenant activo (``users.manage``) y búsqueda de usuarios activos (cualquier sesión).

El admin de instancia ve y edita usuarios de cualquier tenant (también moverlos de tenant); el resto, solo los de su
tenant: uno de otro tenant da 404 (ADR-013).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query, status

from app.api.deps import Context, CurrentUser, DbSession, SettingsDep, UserManager
from app.api.v1.schemas import MAX_PAGE_SIZE, UserBrief, UserCreate, UserLookup, UserOut, UserPage, UserUpdate
from app.db.models import User
from app.domain.identity import users
from app.domain.identity.users import UserChanges
from app.domain.tenancy.errors import PermissionEscalationError

router = APIRouter(prefix="/users", tags=["users"])

_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"description": "No autenticado"},
    403: {"description": "Sin permiso users.manage, permiso que no tienes o token CSRF no válido"},
}


@router.get("", response_model=UserPage, summary="Listar usuarios", responses=_ERRORS)
def list_users(
    manager: UserManager,
    db: DbSession,
    q: Annotated[str | None, Query(max_length=64, description="Texto en usuario o nombre")] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> UserPage:
    """Usuarios del tenant activo ordenados por nombre de usuario."""
    rows, total = users.list_users(db, tenant_id=manager.scope_tenant_id, q=q, limit=limit, offset=offset)
    return UserPage(items=[UserOut.model_validate(u) for u in rows], total=total)


@router.post(
    "",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear usuario",
    responses={
        **_ERRORS,
        400: {"description": "Contraseña no válida"},
        404: {"description": "El rol o el tenant no existen"},
        409: {"description": "El usuario ya existe"},
    },
)
def create_user(body: UserCreate, manager: UserManager, db: DbSession, settings: SettingsDep, ctx: Context) -> UserOut:
    """Crea un usuario activo del tenant activo (o de ``tenant_id``, solo el admin de instancia)."""
    if body.tenant_id is not None and not manager.is_instance_admin:
        raise PermissionEscalationError("Solo un administrador de la instancia elige el tenant.")
    user = users.create_user(
        db,
        username=body.username,
        display_name=body.display_name,
        password=body.password.get_secret_value(),
        settings=settings,
        ctx=ctx,
        actor=manager,
        tenant_id=body.tenant_id if body.tenant_id is not None else manager.scope_tenant_id,
        role_id=body.role_id,
        is_instance_admin=body.is_instance_admin,
    )
    return UserOut.model_validate(user)


@router.get(
    "/lookup",
    response_model=UserLookup,
    summary="Buscar usuarios activos",
    responses={401: {"description": "No autenticado"}},
)
def lookup_users(
    user: CurrentUser,
    db: DbSession,
    q: Annotated[str, Query(min_length=2, max_length=64, description="Inicio del usuario o del nombre")],
) -> UserLookup:
    """Hasta 20 usuarios activos del tenant activo para invitar a un proyecto (cualquier sesión)."""
    found = users.lookup_users(db, tenant_id=user.scope_tenant_id, q=q)
    return UserLookup(items=[UserBrief.model_validate(u) for u in found])


@router.get(
    "/{user_id}",
    response_model=UserOut,
    summary="Ver usuario",
    responses={**_ERRORS, 404: {"description": "No existe"}},
)
def get_user(user_id: int, manager: UserManager, db: DbSession) -> UserOut:
    """Detalle de un usuario."""
    return UserOut.model_validate(users.get_user(db, user_id, tenant_id=_scope(manager)))


def _scope(manager: User) -> int | None:
    """El admin de instancia llega a usuarios de cualquier tenant; el resto, solo al activo."""
    return None if manager.is_instance_admin else manager.scope_tenant_id


@router.patch(
    "/{user_id}",
    response_model=UserOut,
    summary="Editar, desactivar, reactivar, desbloquear o mover usuario",
    responses={
        **_ERRORS,
        400: {"description": "Contraseña no válida"},
        404: {"description": "No existe"},
        409: {"description": "Último administrador, último gestor del tenant o cambio sobre uno mismo"},
    },
)
def update_user(
    user_id: int, body: UserUpdate, manager: UserManager, db: DbSession, settings: SettingsDep, ctx: Context
) -> UserOut:
    """Cambia nombre, rol, estado, contraseña o tenant, o quita un bloqueo. Desactivar, restablecer la contraseña,
    cambiar el rol o el tenant cierra sus sesiones."""
    user = users.get_user(db, user_id, tenant_id=_scope(manager))
    changes = UserChanges(
        display_name=body.display_name,
        role_id=body.role_id,
        is_instance_admin=body.is_instance_admin,
        tenant_id=body.tenant_id,
        is_active=body.is_active,
        password=body.password.get_secret_value() if body.password is not None else None,
        unlock=body.unlock,
    )
    return UserOut.model_validate(users.update_user(db, user, changes, actor=manager, settings=settings, ctx=ctx))
