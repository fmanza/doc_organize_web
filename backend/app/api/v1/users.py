"""``/api/v1/users``: administración de usuarios (solo ``admin``)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query, status

from app.api.deps import AdminUser, Context, DbSession, SettingsDep
from app.api.v1.schemas import MAX_PAGE_SIZE, UserCreate, UserOut, UserPage, UserUpdate
from app.domain.identity import users
from app.domain.identity.users import UserChanges

router = APIRouter(prefix="/users", tags=["users"])

_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"description": "No autenticado"},
    403: {"description": "Sin rol de administrador o token CSRF no válido"},
}


@router.get("", response_model=UserPage, summary="Listar usuarios", responses=_ERRORS)
def list_users(
    _: AdminUser,
    db: DbSession,
    q: Annotated[str | None, Query(max_length=64, description="Texto en usuario o nombre")] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> UserPage:
    """Usuarios ordenados por nombre de usuario."""
    rows, total = users.list_users(db, q=q, limit=limit, offset=offset)
    return UserPage(items=[UserOut.model_validate(u) for u in rows], total=total)


@router.post(
    "",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crear usuario",
    responses={**_ERRORS, 400: {"description": "Contraseña no válida"}, 409: {"description": "El usuario ya existe"}},
)
def create_user(body: UserCreate, admin: AdminUser, db: DbSession, settings: SettingsDep, ctx: Context) -> UserOut:
    """Crea un usuario activo con la contraseña inicial indicada."""
    user = users.create_user(
        db,
        username=body.username,
        display_name=body.display_name,
        password=body.password.get_secret_value(),
        role=body.role,
        settings=settings,
        ctx=ctx,
        actor_id=admin.id,
    )
    return UserOut.model_validate(user)


@router.get(
    "/{user_id}",
    response_model=UserOut,
    summary="Ver usuario",
    responses={**_ERRORS, 404: {"description": "No existe"}},
)
def get_user(user_id: int, _: AdminUser, db: DbSession) -> UserOut:
    """Detalle de un usuario."""
    return UserOut.model_validate(users.get_user(db, user_id))


@router.patch(
    "/{user_id}",
    response_model=UserOut,
    summary="Editar, desactivar, reactivar o desbloquear usuario",
    responses={
        **_ERRORS,
        400: {"description": "Contraseña no válida"},
        404: {"description": "No existe"},
        409: {"description": "Último administrador o autodesactivación"},
    },
)
def update_user(
    user_id: int, body: UserUpdate, admin: AdminUser, db: DbSession, settings: SettingsDep, ctx: Context
) -> UserOut:
    """Cambia nombre, rol, estado o contraseña, o quita un bloqueo. Desactivar o restablecer la contraseña cierra sus
    sesiones."""
    user = users.get_user(db, user_id)
    changes = UserChanges(
        display_name=body.display_name,
        role=body.role,
        is_active=body.is_active,
        password=body.password.get_secret_value() if body.password is not None else None,
        unlock=body.unlock,
    )
    return UserOut.model_validate(users.update_user(db, user, changes, actor=admin, settings=settings, ctx=ctx))
