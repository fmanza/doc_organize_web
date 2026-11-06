"""Contexto y taxonomías (Fase 7): plantillas, contexto del proyecto, manifiesto y acceso al sitio aislado.

Construir (``context_build``) y borrar (``context_delete``) el contexto son runs: ``POST /projects/{id}/runs``. El
sitio se sirve fuera de ``/api`` (``/site/<token>/…``, ``app.api.site``).
"""

from __future__ import annotations

from typing import Annotated, Any
from urllib.parse import quote

from fastapi import APIRouter, Query, Response, status

from app.api.deps import Context, CurrentSession, CurrentUser, DbSession, SettingsDep, TemplateManager
from app.api.v1.listing import ContextDocumentSort, OrderQuery, SearchQuery, listing
from app.api.v1.schemas import (
    MAX_PAGE_SIZE,
    CatalogEntryOut,
    ContextDocumentOut,
    ContextDocumentPage,
    ContextDomainOut,
    ContextOut,
    SiteSessionOut,
    TaxonomyManifestOut,
    TaxonomyMarkdownIn,
    TaxonomyTemplateDetail,
    TaxonomyTemplateList,
    TaxonomyTemplateOut,
)
from app.db.models import ContextDocument
from app.domain.context import service as context
from app.domain.context import site, templates
from app.domain.context.errors import SiteNotFoundError
from app.domain.context.templates import TemplateView
from app.domain.documents.outputs import output_paths
from app.domain.identity.sessions import acting_user
from app.domain.projects import service as projects

router = APIRouter(tags=["context"])

_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"description": "No autenticado"},
    404: {"description": "No encontrado (o sin acceso)"},
}
_TEMPLATE_ERRORS: dict[int | str, dict[str, Any]] = {
    **_ERRORS,
    403: {"description": "Solo administradores"},
    409: {"description": "Plantilla incluida en doc_organize (template_builtin)"},
    422: {"description": "Nombre o Markdown no válidos (template_invalid)"},
}


def _catalog(entries: list[tuple[str, str]]) -> list[CatalogEntryOut]:
    return [CatalogEntryOut(slug=slug, name=name) for slug, name in entries]


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
        domains=_catalog(view.domains),
        material_types=_catalog(view.material_types),
    )


# --- plantillas de taxonomía -----------------------------------------------------------------------------------------


@router.get(
    "/taxonomy-templates",
    response_model=TaxonomyTemplateList,
    summary="Plantillas de taxonomía",
    responses={401: _ERRORS[401]},
)
def list_templates(user: CurrentUser, db: DbSession) -> TaxonomyTemplateList:
    """Incluidas en doc_organize y personalizadas; cualquier usuario las ve para elegir una al construir el contexto."""
    return TaxonomyTemplateList(items=[_template_out(v) for v in templates.list_templates(db, user)])


@router.get(
    "/taxonomy-templates/{name}",
    response_model=TaxonomyTemplateDetail,
    summary="Ver plantilla de taxonomía",
    responses=_ERRORS,
)
def get_template(name: str, user: CurrentUser, db: DbSession) -> TaxonomyTemplateDetail:
    return _template_detail(templates.get_template(db, user, name))


@router.get(
    "/taxonomy-templates/{name}/download",
    response_class=Response,
    summary="Descargar plantilla como Markdown",
    responses={**_ERRORS, 200: {"content": {"text/markdown": {}}, "description": "Plantilla (.md)"}},
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


# --- contexto del proyecto ---------------------------------------------------------------------------------------


@router.get(
    "/projects/{project_id}/context",
    response_model=ContextOut,
    summary="Contexto del proyecto",
    responses=_ERRORS,
)
def get_context(project_id: int, user: CurrentUser, db: DbSession) -> ContextOut:
    """Resumen del último contexto construido (404 ``context_not_found`` si no hay)."""
    access = projects.get_access(db, project_id, user)
    row = context.get_context(db, access.project)
    return ContextOut(
        output_folder_name=row.output_folder_name,
        catalog_kind=row.catalog_kind,
        taxonomy_template_name=row.taxonomy_template_name,
        documents_count=row.documents_count,
        unclassified_count=row.unclassified_count,
        failed_count=row.failed_count,
        collisions_count=row.collisions_count,
        site_built=row.site_built,
        ai_classification=row.ai_classification,
        domains=[ContextDomainOut.model_validate(d) for d in row.domains],
        built_by_run_id=row.built_by_run_id,
        built_at=row.built_at,
    )


def _document_out(row: ContextDocument) -> ContextDocumentOut:
    out = ContextDocumentOut.model_validate(row)
    out.output_path = output_paths(row.folder, row.path).markdown
    return out


@router.get(
    "/projects/{project_id}/context/documents",
    response_model=ContextDocumentPage,
    summary="Documentos del contexto",
    responses=_ERRORS,
)
def list_context_documents(
    project_id: int,
    user: CurrentUser,
    db: DbSession,
    domain: Annotated[
        str | None, Query(max_length=128, description="Slug del dominio; sin él, los documentos sin clasificar")
    ] = None,
    only: Annotated[
        context.DocumentFilter | None,
        Query(description="Solo fallidos o con colisión (G30, contextos construidos con doc_organize 0.13.0)"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    q: SearchQuery = None,
    sort: Annotated[ContextDocumentSort | None, Query(description="Columna por la que ordenar")] = None,
    order: OrderQuery = "asc",
) -> ContextDocumentPage:
    access = projects.get_access(db, project_id, user)
    rows, total = context.list_documents(
        db, access.project, domain=domain, only=only, limit=limit, offset=offset, listing=listing(q, sort, order)
    )
    return ContextDocumentPage(items=[_document_out(r) for r in rows], total=total)


def _manifest_out(manifest: context.Manifest) -> TaxonomyManifestOut:
    return TaxonomyManifestOut(
        markdown=manifest.markdown,
        error=manifest.error,
        domains=_catalog(manifest.info.domains) if manifest.info else [],
        material_types=_catalog(manifest.info.material_types) if manifest.info else [],
    )


@router.get(
    "/projects/{project_id}/context/taxonomy-manifest",
    response_model=TaxonomyManifestOut,
    summary="Manifiesto de taxonomía del proyecto",
    responses={**_ERRORS, 409: {"description": "No es un fichero normal (manifest_replaced)"}},
)
def get_manifest(project_id: int, user: CurrentUser, db: DbSession, settings: SettingsDep) -> TaxonomyManifestOut:
    access = projects.get_access(db, project_id, user)
    return _manifest_out(context.read_manifest(settings, access.project))


@router.put(
    "/projects/{project_id}/context/taxonomy-manifest",
    response_model=TaxonomyManifestOut,
    summary="Guardar manifiesto de taxonomía",
    responses={
        **_ERRORS,
        403: {"description": "Rol insuficiente (editor)"},
        409: {"description": "Escritura en curso (write_locked) o no es un fichero normal (manifest_replaced)"},
        422: {"description": "Markdown no válido (template_invalid) o destino de solo lectura"},
        503: {"description": "Ubicación no disponible"},
    },
)
def put_manifest(
    project_id: int,
    body: TaxonomyMarkdownIn,
    user: CurrentUser,
    db: DbSession,
    settings: SettingsDep,
    ctx: Context,
) -> TaxonomyManifestOut:
    """Valida y escribe ``taxonomy_manifest.md`` en la carpeta del proyecto (lo usa el catálogo «manifiesto»)."""
    access = projects.get_access(db, project_id, user, min_role="editor")
    return _manifest_out(context.save_manifest(db, settings, access.project, body.markdown, actor=user, ctx=ctx))


@router.post(
    "/projects/{project_id}/context/site-session",
    response_model=SiteSessionOut,
    summary="Abrir el sitio del contexto",
    responses={**_ERRORS, 404: {"description": "Sin sitio construido (site_not_found) o sin acceso"}},
)
def open_site(project_id: int, session: CurrentSession, db: DbSession, settings: SettingsDep) -> SiteSessionOut:
    """URL del sitio aislado con un token ligado a esta sesión y a este proyecto (caduca en una hora, ADR-010)."""
    access = projects.get_access(db, project_id, acting_user(session))
    if not site.site_built(db, access.project):
        raise SiteNotFoundError("El contexto no tiene sitio construido.")
    token, expires_at = site.mint_token(settings, access.project, session)
    return SiteSessionOut(url=f"/site/{token}/", expires_at=expires_at)
