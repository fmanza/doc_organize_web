"""``/site/<token>/…``: sitio Zensical del contexto, aislado del origen de la app (WB-7.3, ADR-010).

Fuera de ``/api`` y sin cookie: el acceso lo da el token de ``POST /api/v1/projects/{id}/context/site-session``. Toda
respuesta (también los errores) lleva las cabeceras de ``SITE_HEADERS`` (CSP ``sandbox``, sin ``allow-same-origin``).
"""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter
from fastapi.responses import Response

from app.api.deps import DbSession, SettingsDep
from app.core.errors import problem
from app.domain.context import site
from app.domain.context.errors import SiteNotFoundError
from app.domain.locations.errors import LocationUnavailableError

router = APIRouter(prefix="/site", include_in_schema=False)


def _site_file(token: str, path: str, db: DbSession, settings: SettingsDep) -> Response:
    try:
        project = site.verify_token(db, settings, token)
        found = site.read_site_file(db, settings, project, path)
    except SiteNotFoundError:
        response: Response = problem(404, "No encontrado")
    except LocationUnavailableError:
        response = problem(503, "La ubicación no responde")
    else:
        headers = {"X-Content-Type-Options": "nosniff"}
        if found.download:
            headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(found.name)}"
        response = Response(content=found.content, media_type=found.content_type, headers=headers)
    response.headers.update(site.SITE_HEADERS)
    return response


@router.get("/{token}/{path:path}", response_model=None)
def site_file(token: str, path: str, db: DbSession, settings: SettingsDep) -> Response:
    """Fichero del sitio (``…/`` o una carpeta sirven su ``index.html``)."""
    return _site_file(token, path, db, settings)


@router.get("/{token}", response_model=None)
def site_root(token: str, db: DbSession, settings: SettingsDep) -> Response:
    """Sin barra final las rutas relativas del sitio no funcionarían: redirige a ``/site/<token>/``."""
    response = Response(status_code=308, headers={"Location": f"/site/{quote(token)}/"})
    response.headers.update(site.SITE_HEADERS)
    return response
