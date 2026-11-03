"""``/api/v1/auth``: inicio y cierre de sesión, usuario actual, tenant activo y cambio de contraseña (ADR-003,
ADR-013)."""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import (
    Context,
    CurrentSession,
    CurrentUser,
    DbSession,
    InstanceAdmin,
    SettingsDep,
    clear_auth_cookies,
    set_auth_cookies,
    set_csrf_cookie,
)
from app.api.v1.schemas import (
    CsrfToken,
    LoginRequest,
    Me,
    PasswordChange,
    Permission,
    RoleRef,
    TenantRef,
    TenantSwitch,
)
from app.core.security import new_csrf_token, session_csrf_token
from app.db.models import User
from app.domain.identity import audit, auth
from app.domain.identity.audit import AuditAction
from app.domain.tenancy import tenants

router = APIRouter(prefix="/auth", tags=["auth"])

_401: dict[int | str, dict[str, Any]] = {401: {"description": "No autenticado"}}
_403: dict[int | str, dict[str, Any]] = {403: {"description": "Token CSRF ausente o no válido"}}


@router.get("/csrf", response_model=CsrfToken, summary="Obtener token CSRF")
def get_csrf(request: Request, response: Response, settings: SettingsDep) -> CsrfToken:
    """Devuelve el token CSRF y lo pone en la cookie CSRF.

    Sin sesión es aleatorio (protege el propio login); con cookie de sesión es el ligado a ella.
    """
    session_token = request.cookies.get(settings.session_cookie)
    token = session_csrf_token(settings, session_token) if session_token else new_csrf_token()
    set_csrf_cookie(response, settings, token)
    return CsrfToken(csrf_token=token)


@router.post(
    "/login",
    response_model=Me,
    summary="Iniciar sesión",
    responses={401: {"description": "Credenciales no válidas o cuenta bloqueada"}, **_403},
)
def login(
    body: LoginRequest, request: Request, response: Response, db: DbSession, settings: SettingsDep, ctx: Context
) -> Me:
    """Autentica, rota la sesión y pone las cookies de sesión y CSRF."""
    issued = auth.login(
        db,
        username=body.username,
        password=body.password.get_secret_value(),
        settings=settings,
        ctx=ctx,
        previous_token=request.cookies.get(settings.session_cookie),
    )
    set_auth_cookies(response, settings, issued.token)
    return me_out(db, issued.session.user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Cerrar sesión", responses={**_401, **_403})
def logout(session: CurrentSession, response: Response, db: DbSession, settings: SettingsDep, ctx: Context) -> None:
    """Borra la sesión actual y sus cookies."""
    auth.logout(db, session, ctx=ctx)
    clear_auth_cookies(response, settings)


def me_out(db: Session, user: User) -> Me:
    """``Me`` de ``user`` en su tenant activo."""
    acting = user.tenant if user.scope_tenant_id == user.tenant_id else tenants.get_tenant(db, user.scope_tenant_id)
    return Me(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        tenant=TenantRef.model_validate(user.tenant),
        acting_tenant=TenantRef.model_validate(acting),
        is_instance_admin=user.is_instance_admin,
        role=RoleRef.model_validate(user.role),
        permissions=cast(list[Permission], user.permissions),
    )


@router.get("/me", response_model=Me, summary="Usuario actual", responses=_401)
def me(user: CurrentUser, db: DbSession) -> Me:
    """Usuario de la sesión actual, su tenant activo y sus permisos en él."""
    return me_out(db, user)


@router.put(
    "/tenant",
    response_model=Me,
    summary="Cambiar el tenant activo",
    responses={**_401, **_403, 404: {"description": "El tenant no existe"}},
)
def switch_tenant(body: TenantSwitch, session: CurrentSession, user: InstanceAdmin, db: DbSession, ctx: Context) -> Me:
    """Solo admin de instancia: actúa en ``tenant_id`` (``null``: en el suyo) en esta sesión. Se audita."""
    target = tenants.get_tenant(db, body.tenant_id) if body.tenant_id is not None else user.tenant
    session.acting_tenant_id = None if target.id == user.tenant_id else target.id
    user.act_in(session.acting_tenant_id)
    db.info["tenant_id"] = target.id
    audit.record(
        db,
        action=AuditAction.SESSION_TENANT_SWITCH,
        ctx=ctx,
        actor_id=user.id,
        target_type="tenant",
        target_id=target.id,
    )
    db.commit()
    return me_out(db, user)


@router.post(
    "/password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cambiar mi contraseña",
    responses={400: {"description": "Contraseña actual incorrecta o nueva no válida"}, **_401, **_403},
)
def change_password(
    body: PasswordChange, session: CurrentSession, db: DbSession, settings: SettingsDep, ctx: Context
) -> None:
    """Cambia la contraseña y cierra las demás sesiones del usuario."""
    auth.change_password(
        db,
        session,
        current_password=body.current_password.get_secret_value(),
        new_password=body.new_password.get_secret_value(),
        settings=settings,
        ctx=ctx,
    )
