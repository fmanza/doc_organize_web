"""Contexto del proyecto (Fase 7): resumen, documentos clasificados, historial de construcciones y sobrantes."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query
from pydantic import StringConstraints

from app.api.deps import CurrentUser, DbSession, SettingsDep
from app.api.v1.context._shared import ERRORS, document_out
from app.api.v1.listing import ContextDocumentSort, LimitQuery, OffsetQuery, OrderQuery, SearchQuery, listing
from app.api.v1.schemas import (
    ContextAxisOut,
    ContextAxisValueOut,
    ContextBuildOut,
    ContextChangeOut,
    ContextDocumentPage,
    ContextDomainOut,
    ContextFreshnessOut,
    ContextHistoryOut,
    ContextLeftoverOut,
    ContextOut,
    PromptProvenanceOut,
    VersionGroupOut,
)
from app.domain.context import service as context
from app.domain.projects import service as projects

router = APIRouter(tags=["context"])


@router.get(
    "/projects/{project_id}/context",
    response_model=ContextOut,
    summary="Contexto del proyecto",
    responses=ERRORS,
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
        site_built=row.site_built,
        ai_classification=row.ai_classification,
        built_with_version=row.built_with_version,
        ai_classification_model=row.ai_classification_model,
        ai_enrichment_model=row.ai_enrichment_model,
        domains=[ContextDomainOut.model_validate(d) for d in row.domains],
        taxonomy_axes=_axes_out(row.taxonomy_axes, context.axis_counts(db, row.project_id)),
        ai_provenance=[PromptProvenanceOut.model_validate(item) for item in row.ai_provenance],
        freshness=ContextFreshnessOut.model_validate(row.freshness) if row.freshness else None,
        versions_mode=row.versions_mode,
        versions_across_extensions=row.versions_across_extensions,
        version_groups=[VersionGroupOut.model_validate(group) for group in row.version_groups],
        superseded=list(row.superseded),
        superseded_count=row.superseded_count,
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


#: ``clave:slug`` de un filtro por eje (P10 del plan web): clave de eje de doc_organize y slug en kebab-case.
AXIS_FILTER_PATTERN = r"^[a-z][a-z0-9_]{0,40}:[a-z0-9-]{1,128}$"


AxisFilter = Annotated[str, StringConstraints(pattern=AXIS_FILTER_PATTERN)]


@router.get(
    "/projects/{project_id}/context/documents",
    response_model=ContextDocumentPage,
    summary="Documentos del contexto",
    responses=ERRORS,
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
        Query(description=("Solo fallidos o en los que la IA propuso otro dominio (ai_disagrees, 1.5.0)")),
    ] = None,
    language: Annotated[
        str | None, Query(min_length=2, max_length=8, description="Solo este idioma (ISO 639-1, 1.5.0)")
    ] = None,
    keyword: Annotated[
        str | None, Query(max_length=100, description="Solo si alguna palabra clave contiene este texto (1.5.0)")
    ] = None,
    current: Annotated[
        bool, Query(description="Solo las versiones vigentes (W6): fuera las marcadas como versión antigua")
    ] = False,
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
    limit: LimitQuery = 50,
    offset: OffsetQuery = 0,
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
        current_only=current,
        limit=limit,
        offset=offset,
        listing=listing(q, sort, order),
    )
    axes = context.document_axes(db, access.project.id, [r.seq for r in rows])
    return ContextDocumentPage(items=[document_out(r, axes.get(r.seq)) for r in rows], total=total)


#: Cambios por construcción que devuelve el historial (todos van en «Historial del contexto (Excel)»).
MAX_HISTORY_CHANGES = 200


@router.get(
    "/projects/{project_id}/context/history",
    response_model=ContextHistoryOut,
    summary="Historial del contexto",
    responses={**ERRORS, 503: {"description": "Ubicación de destino no disponible"}},
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


@router.get(
    "/projects/{project_id}/context/leftover",
    response_model=ContextLeftoverOut,
    summary="Contexto a medio guardar",
    responses=ERRORS,
)
def get_context_leftover(
    project_id: int, user: CurrentUser, db: DbSession, settings: SettingsDep
) -> ContextLeftoverOut:
    """Si en el destino hay un contexto que la web no llegó a guardar (construcción interrumpida): su carpeta, para
    ofrecer completarlo («Construir») o borrarlo. ``null`` si hay contexto guardado o no hay restos."""
    access = projects.get_access(db, project_id, user)
    return ContextLeftoverOut(output_folder_name=context.leftover_folder(db, settings, access.project))
