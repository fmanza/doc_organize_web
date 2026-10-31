"""Dependencias comunes de los routers: BD, ajustes, sesión actual, rol admin y CSRF (ADR-003)."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import session_csrf_token, tokens_match
from app.db.models import User, UserSession
from app.db.session import get_session
from app.domain.identity.audit import RequestContext
from app.domain.identity.sessions import resolve_session
from app.domain.settings.service import effective_settings

CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})

DbSession = Annotated[Session, Depends(get_session)]


def get_effective_settings(db: DbSession) -> Settings:
    """Ajustes del proceso con los administrables de ``app_settings`` aplicados (ADR-012), leídos en cada petición."""
    return effective_settings(db, get_settings())


SettingsDep = Annotated[Settings, Depends(get_effective_settings)]


def request_context(request: Request) -> RequestContext:
    """IP y ``User-Agent`` de la petición."""
    return RequestContext(
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


Context = Annotated[RequestContext, Depends(request_context)]


def current_session(request: Request, db: DbSession, settings: SettingsDep) -> UserSession:
    """Sesión válida de la cookie de sesión (``__Host-dow_session``; ``dow_session`` en desarrollo).

    Raises:
        HTTPException: 401 si no hay cookie o la sesión no es válida.
    """
    token = request.cookies.get(settings.session_cookie)
    session = resolve_session(db, token, settings) if token else None
    if session is None:
        raise HTTPException(status_code=401, detail="No autenticado")
    return session


CurrentSession = Annotated[UserSession, Depends(current_session)]


def current_user(session: CurrentSession) -> User:
    """Usuario de la sesión actual."""
    return session.user


CurrentUser = Annotated[User, Depends(current_user)]


def require_admin(user: CurrentUser) -> User:
    """Usuario actual con rol ``admin``.

    Raises:
        HTTPException: 403 si no es administrador.
    """
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Se necesita el rol de administrador")
    return user


AdminUser = Annotated[User, Depends(require_admin)]


def csrf_protect(request: Request, settings: SettingsDep) -> None:
    """Doble envío firmado en métodos no seguros.

    La cabecera ``X-CSRF-Token`` debe coincidir con la cookie CSRF; con sesión, además, con
    ``HMAC(clave, token_de_sesión)``.

    Raises:
        HTTPException: 403 si falta o no coincide.
    """
    if request.method in SAFE_METHODS:
        return
    header = request.headers.get(CSRF_HEADER, "")
    cookie = request.cookies.get(settings.csrf_cookie, "")
    if not header or not cookie or not tokens_match(header, cookie):
        raise HTTPException(status_code=403, detail="Token CSRF ausente o no válido")
    session_token = request.cookies.get(settings.session_cookie)
    if session_token and not tokens_match(header, session_csrf_token(settings, session_token)):
        raise HTTPException(status_code=403, detail="Token CSRF ausente o no válido")


def set_auth_cookies(response: Response, settings: Settings, session_token: str) -> str:
    """Pone la cookie de sesión (``HttpOnly``) y la CSRF (legible por la SPA); devuelve el token CSRF."""
    max_age = settings.session_absolute_hours * 3600
    csrf = session_csrf_token(settings, session_token)
    response.set_cookie(
        settings.session_cookie,
        session_token,
        max_age=max_age,
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )
    set_csrf_cookie(response, settings, csrf, max_age=max_age)
    return csrf


def set_csrf_cookie(response: Response, settings: Settings, token: str, *, max_age: int | None = None) -> None:
    """Cookie CSRF sin ``HttpOnly`` para que la SPA la copie en la cabecera."""
    response.set_cookie(
        settings.csrf_cookie,
        token,
        max_age=max_age,
        path="/",
        secure=settings.cookie_secure,
        httponly=False,
        samesite="lax",
    )


def clear_auth_cookies(response: Response, settings: Settings) -> None:
    """Borra las cookies de sesión y CSRF."""
    for name, httponly in ((settings.session_cookie, True), (settings.csrf_cookie, False)):
        response.delete_cookie(name, path="/", secure=settings.cookie_secure, httponly=httponly, samesite="lax")
