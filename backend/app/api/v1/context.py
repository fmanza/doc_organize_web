"""Contexto y taxonomías (Fase 7): plantillas, contexto del proyecto, manifiesto y acceso al sitio aislado.

Construir (``context_build``) y borrar (``context_delete``) el contexto son runs: ``POST /projects/{id}/runs``. El
sitio se sirve fuera de ``/api`` (``/site/<token>/…``, ``app.api.site``).
"""

from __future__ import annotations

from typing import Annotated, Any
from urllib.parse import quote

from fastapi import APIRouter, Header, Query, Response, status
from pydantic import StringConstraints

from app.api.deps import Context, CurrentSession, CurrentUser, DbSession, SettingsDep, TemplateManager
from app.api.v1.listing import ContextDocumentSort, OrderQuery, SearchQuery, listing
from app.api.v1.schemas import (
    MAX_PAGE_SIZE,
    AxisValueOut,
    CatalogEntryOut,
    ContextAxisOut,
    ContextAxisValueOut,
    ContextBuildOut,
    ContextChangeOut,
    ContextDocumentOut,
    ContextDocumentPage,
    ContextDomainOut,
    ContextFreshnessOut,
    ContextHistoryOut,
    ContextOut,
    FrontMatterReportOut,
    ManifestVersionDetail,
    ManifestVersionList,
    ManifestVersionOut,
    ProfileSectionsOut,
    ProjectProfileIn,
    ProjectProfileOut,
    PromptMessageOut,
    PromptPreviewIn,
    PromptPreviewOut,
    PromptProvenanceOut,
    SiteSessionOut,
    TaxonomyAxisSummaryOut,
    TaxonomyManifestOut,
    TaxonomyMarkdownIn,
    TaxonomyTemplateDetail,
    TaxonomyTemplateList,
    TaxonomyTemplateOut,
    TemplatePromptPreviewIn,
)
from app.db.models import ContextDocument, ContextDocumentAxisValue
from app.domain.context import manifest_versions, site, templates
from app.domain.context import profile as profiles
from app.domain.context import service as context
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


def _front_matter(info: Any) -> FrontMatterReportOut:
    """Ejes y avisos del front matter (``TemplateInfo``, W3); vacío sin catálogo válido."""
    if info is None:
        return FrontMatterReportOut()
    return FrontMatterReportOut(
        axes=[
            TaxonomyAxisSummaryOut(
                key=axis.key, name=axis.name, organizes=axis.organizes, multiple=axis.multiple, values=axis.values
            )
            for axis in info.axes
        ],
        implicit_axes=info.implicit_axes,
        ignored_keys=info.ignored_keys,
        legacy_format=info.legacy_format,
    )


def _template_detail(view: TemplateView) -> TaxonomyTemplateDetail:
    return TaxonomyTemplateDetail(
        **_template_out(view).model_dump(),
        markdown=view.markdown or "",
        domains=_catalog(view.domains),
        material_types=_catalog(view.material_types),
        front_matter=_front_matter(view.info),
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
        built_with_version=row.built_with_version,
        ai_classification_model=row.ai_classification_model,
        ai_enrichment_model=row.ai_enrichment_model,
        domains=[ContextDomainOut.model_validate(d) for d in row.domains],
        taxonomy_axes=_axes_out(row.taxonomy_axes, context.axis_counts(db, row.project_id)),
        ai_provenance=[PromptProvenanceOut.model_validate(item) for item in row.ai_provenance],
        freshness=ContextFreshnessOut.model_validate(row.freshness) if row.freshness else None,
        built_by_run_id=row.built_by_run_id,
        built_at=row.built_at,
    )


def _axes_out(axes: list[dict[str, Any]], counts: dict[tuple[str, str], int]) -> list[ContextAxisOut]:
    """Ejes de ``project_contexts.taxonomy_axes`` con cuántos documentos tiene cada valor."""
    return [
        ContextAxisOut(
            key=axis["key"],
            name=axis["name"],
            description=axis.get("description"),
            multiple=bool(axis.get("multiple")),
            organizes=axis.get("organizes"),
            values=[
                ContextAxisValueOut(
                    slug=value["slug"], name=value["name"], documents=counts.get((axis["key"], value["slug"]), 0)
                )
                for value in axis.get("values", [])
            ],
        )
        for axis in axes
    ]


def _document_out(row: ContextDocument, axes: list[ContextDocumentAxisValue] | None = None) -> ContextDocumentOut:
    out = ContextDocumentOut.model_validate(row)
    out.output_path = output_paths(row.folder, row.path).markdown
    grouped: dict[str, list[AxisValueOut]] = {}
    for value in axes or []:
        grouped.setdefault(value.axis, []).append(AxisValueOut.model_validate(value))
    out.axes = grouped
    return out


#: ``clave:slug`` de un filtro por eje (P10 del plan web): clave de eje de doc_organize y slug en kebab-case.
AXIS_FILTER_PATTERN = r"^[a-z][a-z0-9_]{0,40}:[a-z0-9-]{1,128}$"
AxisFilter = Annotated[str, StringConstraints(pattern=AXIS_FILTER_PATTERN)]


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
        Query(
            description=(
                "Solo fallidos, con colisión (G30, contextos de doc_organize 0.13.0) o en los que la IA propuso otro "
                "dominio (ai_disagrees, 1.5.0)"
            )
        ),
    ] = None,
    language: Annotated[
        str | None, Query(min_length=2, max_length=8, description="Solo este idioma (ISO 639-1, 1.5.0)")
    ] = None,
    keyword: Annotated[
        str | None, Query(max_length=100, description="Solo si alguna palabra clave contiene este texto (1.5.0)")
    ] = None,
    axis: Annotated[
        list[AxisFilter] | None,
        Query(
            max_length=context.MAX_AXIS_FILTERS,
            description=(
                "Filtro por eje ``clave:slug`` (W3), repetible hasta 20: valores del mismo eje con O, ejes distintos "
                "con Y. Un eje o valor que no existe da una lista vacía"
            ),
        ),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    q: SearchQuery = None,
    sort: Annotated[ContextDocumentSort | None, Query(description="Columna por la que ordenar")] = None,
    order: OrderQuery = "asc",
) -> ContextDocumentPage:
    """Documentos de un dominio o sin clasificar; ``q`` busca en título, rutas, tipo, autor y descripción."""
    access = projects.get_access(db, project_id, user)
    rows, total = context.list_documents(
        db,
        access.project,
        domain=domain,
        only=only,
        language=language,
        keyword=keyword,
        axes=context.parse_axis_filters(axis or []),
        limit=limit,
        offset=offset,
        listing=listing(q, sort, order),
    )
    axes = context.document_axes(db, access.project.id, [r.seq for r in rows])
    return ContextDocumentPage(items=[_document_out(r, axes.get(r.seq)) for r in rows], total=total)


#: Cambios por construcción que devuelve el historial (todos van en «Historial del contexto (Excel)»).
MAX_HISTORY_CHANGES = 200


@router.get(
    "/projects/{project_id}/context/history",
    response_model=ContextHistoryOut,
    summary="Historial del contexto",
    responses={**_ERRORS, 503: {"description": "Ubicación de destino no disponible"}},
)
def get_context_history(
    project_id: int,
    user: CurrentUser,
    db: DbSession,
    settings: SettingsDep,
    limit: Annotated[int, Query(ge=1, le=50, description="Construcciones más recientes que se devuelven")] = 10,
) -> ContextHistoryOut:
    """Últimas construcciones del contexto con sus cambios (1.5.0), para cualquier miembro.

    Sale de ``historial_contexto/CONTEXT_HISTORY.jsonl``, que se conserva al borrar el contexto. Cada construcción lleva
    como mucho los primeros 200 cambios (``changes_total`` dice cuántos hay), con rutas relativas a las carpetas de
    origen.
    """
    access = projects.get_access(db, project_id, user)
    history = context.read_history(settings, access.project, limit=limit, max_changes=MAX_HISTORY_CHANGES)
    return ContextHistoryOut(
        items=[
            ContextBuildOut(
                built_at=build.built_at,
                previous_built_at=build.previous_built_at,
                built_with_version=build.built_with_version,
                taxonomy_manifest_used=build.taxonomy_manifest_used,
                ai_classification_model=build.ai_classification_model,
                ai_enrichment_model=build.ai_enrichment_model,
                classified=build.classified,
                unclassified=build.unclassified,
                changes_total=total,
                changes=[
                    ContextChangeOut(path=change.source_path, **_change_fields(change)) for change in build.changes
                ],
            )
            for build, total in history.builds
        ],
        total=history.total,
        error=history.error,
    )


def _change_fields(change: Any) -> dict[str, Any]:
    return {
        "change": change.change,
        "previous_domain": change.previous_domain,
        "domain": change.domain,
        "previous_material_type": change.previous_material_type,
        "material_type": change.material_type,
        "classified_by": change.classified_by,
    }


def _manifest_out(manifest: context.Manifest, db: DbSession, project_id: int) -> TaxonomyManifestOut:
    return TaxonomyManifestOut(
        markdown=manifest.markdown,
        error=manifest.error,
        domains=_catalog(manifest.info.domains) if manifest.info else [],
        material_types=_catalog(manifest.info.material_types) if manifest.info else [],
        front_matter=_front_matter(manifest.info),
        etag=manifest.etag,
        last_changed_at=manifest_versions.latest_version_at(db, project_id),
    )


IfMatch = Annotated[
    str | None,
    Header(description="``etag`` del manifiesto leído (``GET …/taxonomy-manifest``); obligatorio al cambiarlo"),
]

_MANIFEST_WRITE_ERRORS: dict[int | str, dict[str, Any]] = {
    **_ERRORS,
    403: {"description": "Rol insuficiente (editor)"},
    409: {
        "description": "Cambió desde que se leyó (manifest_changed), escritura en curso (write_locked) o no es un "
        "fichero normal (manifest_replaced)"
    },
    422: {"description": "Markdown no válido (template_invalid) o destino de solo lectura"},
    428: {"description": "Falta If-Match (etag_required)"},
    503: {"description": "Ubicación no disponible"},
}


@router.get(
    "/projects/{project_id}/context/taxonomy-manifest",
    response_model=TaxonomyManifestOut,
    summary="Manifiesto de taxonomía del proyecto",
    responses={**_ERRORS, 409: {"description": "No es un fichero normal (manifest_replaced)"}},
)
def get_manifest(project_id: int, user: CurrentUser, db: DbSession, settings: SettingsDep) -> TaxonomyManifestOut:
    access = projects.get_access(db, project_id, user)
    return _manifest_out(context.read_manifest(settings, access.project), db, project_id)


@router.put(
    "/projects/{project_id}/context/taxonomy-manifest",
    response_model=TaxonomyManifestOut,
    summary="Guardar manifiesto de taxonomía",
    responses=_MANIFEST_WRITE_ERRORS,
)
def put_manifest(
    project_id: int,
    body: TaxonomyMarkdownIn,
    user: CurrentUser,
    db: DbSession,
    settings: SettingsDep,
    ctx: Context,
    if_match: IfMatch = None,
) -> TaxonomyManifestOut:
    """Valida y escribe ``taxonomy_manifest.md`` (lo usa el catálogo «manifiesto»), guardando antes como versión lo
    que había. El mismo texto no escribe ni crea versión."""
    access = projects.get_access(db, project_id, user, min_role="editor")
    saved = context.save_manifest(db, settings, access.project, body.markdown, if_match=if_match, actor=user, ctx=ctx)
    return _manifest_out(saved, db, project_id)


@router.delete(
    "/projects/{project_id}/context/taxonomy-manifest",
    response_model=TaxonomyManifestOut,
    summary="Borrar manifiesto de taxonomía",
    responses={**_MANIFEST_WRITE_ERRORS, 404: {"description": "Sin acceso o sin manifiesto (manifest_not_found)"}},
)
def delete_manifest(
    project_id: int,
    user: CurrentUser,
    db: DbSession,
    settings: SettingsDep,
    ctx: Context,
    if_match: IfMatch = None,
) -> TaxonomyManifestOut:
    """Borra ``taxonomy_manifest.md`` guardando antes su versión (se puede restaurar)."""
    access = projects.get_access(db, project_id, user, min_role="editor")
    deleted = context.delete_manifest(db, settings, access.project, if_match=if_match, actor=user, ctx=ctx)
    return _manifest_out(deleted, db, project_id)


def _version_fields(version: manifest_versions.VersionSummary) -> dict[str, Any]:
    return {
        "id": version.id,
        "created_at": version.created_at,
        "created_by": version.created_by,
        "action": version.action,
        "empty": version.empty,
        "valid": version.valid,
        "domains": version.domains,
        "material_types": version.material_types,
    }


@router.get(
    "/projects/{project_id}/context/taxonomy-manifest/versions",
    response_model=ManifestVersionList,
    summary="Versiones anteriores del manifiesto",
    responses=_ERRORS,
)
def list_manifest_versions(project_id: int, user: CurrentUser, db: DbSession) -> ManifestVersionList:
    """Las últimas versiones (lo que había antes de cada cambio), de la más reciente a la más antigua, sin el texto."""
    projects.get_access(db, project_id, user)
    return ManifestVersionList(
        items=[ManifestVersionOut(**_version_fields(v)) for v in manifest_versions.list_versions(db, project_id)],
        limit=manifest_versions.MAX_MANIFEST_VERSIONS,
    )


@router.get(
    "/projects/{project_id}/context/taxonomy-manifest/versions/{version_id}",
    response_model=ManifestVersionDetail,
    summary="Texto de una versión del manifiesto",
    responses={**_ERRORS, 404: {"description": "Sin acceso o versión inexistente (manifest_version_not_found)"}},
)
def get_manifest_version(project_id: int, version_id: int, user: CurrentUser, db: DbSession) -> ManifestVersionDetail:
    projects.get_access(db, project_id, user)
    stored = manifest_versions.get_version(db, project_id, version_id)  # 404 si no es de este proyecto
    summary = next(v for v in manifest_versions.list_versions(db, project_id) if v.id == stored.id)
    return ManifestVersionDetail(**_version_fields(summary), markdown=stored.markdown)


@router.post(
    "/projects/{project_id}/context/taxonomy-manifest/versions/{version_id}/restore",
    response_model=TaxonomyManifestOut,
    summary="Restaurar una versión del manifiesto",
    responses={
        **_MANIFEST_WRITE_ERRORS,
        404: {"description": "Sin acceso o versión inexistente (manifest_version_not_found)"},
        422: {"description": "Versión no válida (manifest_version_invalid) o destino de solo lectura"},
    },
)
def restore_manifest_version(
    project_id: int,
    version_id: int,
    user: CurrentUser,
    db: DbSession,
    settings: SettingsDep,
    ctx: Context,
    if_match: IfMatch = None,
) -> TaxonomyManifestOut:
    """Restaura la versión (una «sin manifiesto» borra el fichero), guardando antes lo que había: se puede deshacer."""
    access = projects.get_access(db, project_id, user, min_role="editor")
    restored = context.restore_manifest(
        db, settings, access.project, version_id, if_match=if_match, actor=user, ctx=ctx
    )
    return _manifest_out(restored, db, project_id)


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


# --- perfil del proyecto y vista previa del prompt (W3) ---------------------------------------------------------------


def _sections_out(sections: Any) -> ProfileSectionsOut | None:
    if sections is None:
        return None
    return ProfileSectionsOut(
        context=sections.context,
        tie_breakers=sections.tie_breakers,
        glossary=sections.glossary,
        examples=list(sections.examples),
    )


def _profile_out(profile: profiles.Profile) -> ProjectProfileOut:
    return ProjectProfileOut(markdown=profile.markdown, sections=_sections_out(profile.sections), etag=profile.etag)


def _preview_out(preview: Any) -> PromptPreviewOut:
    return PromptPreviewOut(
        messages=[PromptMessageOut(role=role, content=content) for role, content in preview.messages],
        template_profile=_sections_out(preview.template_profile),
        project_profile=_sections_out(preview.project_profile),
        profile=_sections_out(preview.profile),
    )


_PROFILE_WRITE_ERRORS: dict[int | str, dict[str, Any]] = {
    **_ERRORS,
    403: {"description": "Rol insuficiente (editor)"},
    409: {
        "description": "Cambió desde que se leyó (profile_changed), escritura en curso (write_locked) o no es un "
        "fichero normal (profile_replaced)"
    },
    422: {"description": "Demasiado grande (profile_invalid) o destino de solo lectura"},
    428: {"description": "Falta If-Match (etag_required)"},
    503: {"description": "Ubicación no disponible"},
}


@router.get(
    "/projects/{project_id}/context/profile",
    response_model=ProjectProfileOut,
    summary="Perfil del proyecto",
    responses=_ERRORS,
)
def get_profile(project_id: int, user: CurrentUser, db: DbSession, settings: SettingsDep) -> ProjectProfileOut:
    """``.doc_organize/profile.md`` del proyecto y las secciones que reconoce doc_organize."""
    access = projects.get_access(db, project_id, user)
    return _profile_out(profiles.read_profile(settings, access.project))


@router.put(
    "/projects/{project_id}/context/profile",
    response_model=ProjectProfileOut,
    summary="Guardar el perfil del proyecto",
    responses=_PROFILE_WRITE_ERRORS,
)
def put_profile(
    project_id: int,
    body: ProjectProfileIn,
    user: CurrentUser,
    db: DbSession,
    settings: SettingsDep,
    ctx: Context,
    if_match: IfMatch = None,
) -> ProjectProfileOut:
    """Escribe el perfil propio del proyecto (D11: se añade al de la plantilla o el manifiesto). Propietario o editor,
    con el destino ``rw``; auditado sin el texto."""
    access = projects.get_access(db, project_id, user, min_role="editor")
    saved = profiles.save_profile(db, settings, access.project, body.markdown, if_match=if_match, actor=user, ctx=ctx)
    return _profile_out(saved)


@router.delete(
    "/projects/{project_id}/context/profile",
    response_model=ProjectProfileOut,
    summary="Borrar el perfil del proyecto",
    responses=_PROFILE_WRITE_ERRORS,
)
def delete_profile(
    project_id: int, user: CurrentUser, db: DbSession, settings: SettingsDep, ctx: Context, if_match: IfMatch = None
) -> ProjectProfileOut:
    """Borra ``profile.md`` (queda solo el perfil de la plantilla o el manifiesto)."""
    access = projects.get_access(db, project_id, user, min_role="editor")
    return _profile_out(profiles.delete_profile(db, settings, access.project, if_match=if_match, actor=user, ctx=ctx))


@router.post(
    "/projects/{project_id}/context/prompt-preview",
    response_model=PromptPreviewOut,
    summary="Vista previa del prompt de clasificación",
    responses={**_ERRORS, 422: {"description": "Sin manifiesto o no válido (prompt_preview_invalid)"}},
)
def preview_prompt(
    project_id: int, body: PromptPreviewIn, user: CurrentUser, db: DbSession, settings: SettingsDep
) -> PromptPreviewOut:
    """Los mensajes que recibiría el modelo al clasificar con la plantilla o el manifiesto y el perfil (el borrador
    del formulario o el guardado), **sin llamarlo**."""
    access = projects.get_access(db, project_id, user)
    preview = profiles.preview(
        db,
        settings,
        access.project,
        user,
        catalog=body.catalog,
        template_name=body.template_name,
        profile_markdown=body.profile_markdown,
    )
    return _preview_out(preview)


@router.post(
    "/taxonomy-templates/prompt-preview",
    response_model=PromptPreviewOut,
    summary="Vista previa del prompt de una plantilla",
    responses={**_ERRORS, 422: {"description": "Plantilla no válida (template_invalid)"}},
)
def preview_template_prompt(body: TemplatePromptPreviewIn, admin: TemplateManager) -> PromptPreviewOut:
    """Los mensajes que recibiría el modelo con esta plantilla y su perfil (``templates.manage``), sin llamarlo."""
    del admin
    return _preview_out(profiles.template_preview(body.markdown))
