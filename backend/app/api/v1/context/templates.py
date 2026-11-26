"""Plantillas de taxonomía (Fase 7): catálogo, descarga, alta y borrado (solo administradores)."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Response, status

from app.api.deps import Context, CurrentUser, DbSession, TemplateManager
from app.api.v1.context._shared import ERRORS, catalog, front_matter
from app.api.v1.schemas import (
    TaxonomyMarkdownIn,
    TaxonomyTemplateDetail,
    TaxonomyTemplateList,
    TaxonomyTemplateOut,
)
from app.domain.context import templates
from app.domain.context.templates import TemplateView

router = APIRouter(tags=["context"])


_TEMPLATE_ERRORS: dict[int | str, dict[str, Any]] = {
    **ERRORS,
    403: {"description": "Solo administradores"},
    409: {"description": "Plantilla incluida en doc_organize (template_builtin)"},
    422: {"description": "Nombre o Markdown no válidos (template_invalid)"},
}


def _template_out(view: TemplateView) -> TaxonomyTemplateOut:
    return TaxonomyTemplateOut(
        name=view.name,
        title=view.title,
        description=view.description,
        builtin=view.builtin,
        updated_at=view.updated_at,
    )


def _template_detail(view: TemplateView) -> TaxonomyTemplateDetail:
    return TaxonomyTemplateDetail(
        **_template_out(view).model_dump(),
        markdown=view.markdown or "",
        domains=catalog(view.domains),
        material_types=catalog(view.material_types),
        front_matter=front_matter(view.info),
    )


@router.get(
    "/taxonomy-templates",
    response_model=TaxonomyTemplateList,
    summary="Plantillas de taxonomía",
    responses={401: ERRORS[401]},
)
def list_templates(user: CurrentUser, db: DbSession) -> TaxonomyTemplateList:
    """Incluidas en doc_organize y personalizadas; cualquier usuario las ve para elegir una al construir el contexto."""
    return TaxonomyTemplateList(items=[_template_out(v) for v in templates.list_templates(db, user)])


@router.get(
    "/taxonomy-templates/{name}",
    response_model=TaxonomyTemplateDetail,
    summary="Ver plantilla de taxonomía",
    responses=ERRORS,
)
def get_template(name: str, user: CurrentUser, db: DbSession) -> TaxonomyTemplateDetail:
    return _template_detail(templates.get_template(db, user, name))


@router.get(
    "/taxonomy-templates/{name}/download",
    response_class=Response,
    summary="Descargar plantilla como Markdown",
    responses={**ERRORS, 200: {"content": {"text/markdown": {}}, "description": "Plantilla (.md)"}},
)
def download_template(name: str, user: CurrentUser, db: DbSession) -> Response:
    """Mejora opcional de la Fase 7: el Markdown de la plantilla como fichero ``<nombre>.md``."""
    view = templates.get_template(db, user, name)
    return Response(
        content=(view.markdown or "").encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(view.name)}.md"},
    )


@router.put(
    "/taxonomy-templates/{name}",
    response_model=TaxonomyTemplateDetail,
    summary="Crear o sustituir plantilla de taxonomía",
    responses=_TEMPLATE_ERRORS,
)
def put_template(
    name: str, body: TaxonomyMarkdownIn, admin: TemplateManager, db: DbSession, ctx: Context, response: Response
) -> TaxonomyTemplateDetail:
    """Valida el Markdown con doc_organize y guarda la plantilla personalizada (201 si es nueva)."""
    view, created = templates.save_template(db, admin, name, body.markdown, ctx=ctx)
    if created:
        response.status_code = status.HTTP_201_CREATED
    return _template_detail(view)


@router.delete(
    "/taxonomy-templates/{name}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Borrar plantilla de taxonomía",
    responses=_TEMPLATE_ERRORS,
)
def delete_template(name: str, admin: TemplateManager, db: DbSession, ctx: Context) -> None:
    templates.delete_template(db, admin, name, ctx=ctx)
