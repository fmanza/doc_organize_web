"""Sitio Zensical del contexto servido aislado (WB-7.3, ADR-010; decisión C1 del mantenedor).

El sitio es contenido no confiable (el HTML incrustado en los documentos llega tal cual). Se sirve bajo
``/site/<token>/…`` con una CSP ``sandbox`` sin ``allow-same-origin``: sus scripts corren en un origen opaco, sin las
cookies ni el almacenamiento de la app. Como un documento en sandbox no envía la cookie de sesión (``SameSite=Lax``), el
acceso va en la URL: un token firmado con ``app_secret_key``, ligado al proyecto y a la sesión, que caduca en
``SITE_TOKEN_TTL``. Cada petición comprueba la firma, la caducidad, que la sesión siga activa y que el usuario siga
siendo miembro del proyecto. Cualquier fallo da el mismo 404.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Final

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import sign, tokens_match
from app.db.models import Project, ProjectContext, UserSession, utcnow
from app.domain.context.errors import SiteNotFoundError
from app.domain.documents.errors import OutputNotFoundError, OutputTooLargeError
from app.domain.documents.service import read_inside
from app.domain.identity.sessions import is_expired
from app.domain.locations.errors import FolderNotFoundError, InvalidRelativePathError
from app.domain.locations.paths import normalize_relative, resolve_within, run_with_timeout
from app.domain.projects import service as projects
from app.domain.projects.errors import ProjectForbiddenError, ProjectNotFoundError
from app.integrations.doc_organize import context as library

SITE_TOKEN_TTL: Final = timedelta(hours=1)
SIGN_PURPOSE: Final = "context-site-token"
#: Tamaño máximo de un fichero del sitio (el índice del buscador crece con el número de documentos).
MAX_SITE_FILE_BYTES: Final = 64 * 1024 * 1024
#: Tipos que se sirven en línea; el resto se descarga como ``application/octet-stream``.
SITE_TYPES: Final[dict[str, str]] = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".json": "application/json",
    ".map": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".ico": "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
    ".txt": "text/plain; charset=utf-8",
    ".xml": "application/xml",
}
DOWNLOAD_TYPE: Final = "application/octet-stream"
#: Cabeceras de toda respuesta bajo ``/site/`` (también los errores): sustituyen a las de la SPA.
SITE_HEADERS: Final[dict[str, str]] = {
    "Content-Security-Policy": (
        "sandbox allow-scripts allow-popups; default-src 'self'; script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; connect-src 'self'; "
        "worker-src 'self' blob:; object-src 'none'; form-action 'none'; base-uri 'self'; frame-ancestors 'self'"
    ),
    "X-Frame-Options": "SAMEORIGIN",
    "Referrer-Policy": "no-referrer",
    # El documento en sandbox tiene un origen opaco: sus CSS, JS e imágenes son peticiones de otro origen.
    "Cross-Origin-Resource-Policy": "cross-origin",
    "Access-Control-Allow-Origin": "*",
    # Nada en la caché del navegador: al cerrar la sesión el sitio deja de verse (también lo ya visitado).
    "Cache-Control": "no-store",
    # Una pestaña nueva con CSP sandbox y COOP distinto de unsafe-none da error de red (el de la SPA es same-origin).
    "Cross-Origin-Opener-Policy": "unsafe-none",
}


@dataclass(frozen=True)
class SiteFile:
    """Fichero del sitio con su ``Content-Type``; ``download`` si no es de los que se sirven en línea."""

    name: str
    content: bytes
    content_type: str
    download: bool = False


def _message(project_id: int, session: UserSession, expires: int) -> str:
    # El hash del token de sesión liga el token del sitio a esa sesión aunque su id se reutilice tras borrarla.
    return f"site|{project_id}|{session.id}|{session.token_hash}|{expires}"


def mint_token(settings: Settings, project: Project, session: UserSession) -> tuple[str, datetime]:
    """Token del sitio de ``project`` para ``session`` y su caducidad (nunca más allá de la de la sesión)."""
    expires_at = min(utcnow() + SITE_TOKEN_TTL, session.expires_at)
    expires = int(expires_at.timestamp())
    signature = sign(settings, SIGN_PURPOSE, _message(project.id, session, expires))
    return f"{project.id}.{session.id}.{expires}.{signature}", expires_at


def verify_token(db: Session, settings: Settings, token: str) -> Project:
    """Proyecto al que da acceso ``token``.

    Raises:
        SiteNotFoundError: Token mal formado, firma incorrecta, caducado, sesión cerrada o sin acceso al proyecto.
    """
    parts = token.split(".")
    if len(parts) != 4 or not all(p.isdigit() for p in parts[:3]):
        raise SiteNotFoundError()
    project_id, session_id, expires = (int(p) for p in parts[:3])
    now = utcnow()
    if expires <= int(now.timestamp()):
        raise SiteNotFoundError()
    session = db.get(UserSession, session_id)
    if session is None or is_expired(session, settings, now) or not session.user.is_active:
        raise SiteNotFoundError()
    if not tokens_match(parts[3], sign(settings, SIGN_PURPOSE, _message(project_id, session, expires))):
        raise SiteNotFoundError()
    try:
        return projects.get_access(db, project_id, session.user).project
    except (ProjectNotFoundError, ProjectForbiddenError):
        raise SiteNotFoundError() from None


def site_built(db: Session, project: Project) -> bool:
    context = db.get(ProjectContext, project.id)
    return context is not None and context.site_built


def _is_dir_no_link(path: Path) -> bool:
    try:
        return stat.S_ISDIR(os.lstat(path).st_mode)
    except OSError:
        return False


def read_site_file(db: Session, settings: Settings, project: Project, path: str) -> SiteFile:
    """Fichero ``path`` del sitio construido del proyecto (un directorio sirve su ``index.html``).

    Pasa por el resolvedor de ubicaciones; ``site/`` debe ser una carpeta real dentro de la del proyecto y el
    fichero, una vez abierto, seguir dentro de ella (``read_inside``: sin enlaces simbólicos).

    Raises:
        SiteNotFoundError: Sin sitio, ruta no válida, inexistente, fuera del sitio o demasiado grande.
        LocationUnavailableError: El destino no responde.
    """
    if not site_built(db, project):
        raise SiteNotFoundError()
    try:
        clean = normalize_relative(path)
    except InvalidRelativePathError:
        raise SiteNotFoundError() from None
    destination = project.destination_location
    timeout = settings.location_probe_timeout_seconds
    try:
        output = resolve_within(Path(destination.container_path), project.destination_subpath, timeout=timeout)
    except FolderNotFoundError:
        raise SiteNotFoundError() from None
    root = library.site_dir(output.absolute)

    def _read() -> tuple[Path, bytes]:
        if not _is_dir_no_link(root):
            raise SiteNotFoundError()
        target = root / clean if clean else root
        if not clean or path.endswith("/") or _is_dir_no_link(target):
            target = target / "index.html"
        try:
            return target, read_inside(target, root, max_bytes=MAX_SITE_FILE_BYTES)
        except (OutputNotFoundError, OutputTooLargeError):
            raise SiteNotFoundError() from None

    target, data = run_with_timeout(_read, timeout)
    suffix = PurePosixPath(target.name).suffix.lower()
    content_type = SITE_TYPES.get(suffix)
    if content_type is None:
        return SiteFile(name=target.name, content=data, content_type=DOWNLOAD_TYPE, download=True)
    return SiteFile(name=target.name, content=data, content_type=content_type)
