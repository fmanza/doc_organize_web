"""Respuestas de error y conversores compartidos por los routers de contexto."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Header

from app.api.v1.schemas import (
    AxisValueOut,
    CatalogEntryOut,
    ContextDocumentOut,
    FrontMatterReportOut,
    ReviewDocumentOut,
    TaxonomyAxisSummaryOut,
)
from app.db.models import ContextDocument, ContextDocumentAxisValue
from app.domain.documents.outputs import output_paths

ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"description": "No autenticado"},
    404: {"description": "No encontrado (o sin acceso)"},
}


def catalog(entries: list[tuple[str, str]]) -> list[CatalogEntryOut]:
    return [CatalogEntryOut(slug=slug, name=name) for slug, name in entries]


def front_matter(info: Any) -> FrontMatterReportOut:
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


def document_out(row: ContextDocument, axes: list[ContextDocumentAxisValue] | None = None) -> ContextDocumentOut:
    out = ContextDocumentOut.model_validate(row)
    out.output_path = output_paths(row.folder, row.path).markdown
    grouped: dict[str, list[AxisValueOut]] = {}
    for value in axes or []:
        grouped.setdefault(value.axis, []).append(AxisValueOut.model_validate(value))
    out.axes = grouped
    return out


def review_document_out(doc: ContextDocument, axes: list[ContextDocumentAxisValue] | None) -> ReviewDocumentOut:
    """El documento de una fila de revisión o de una propuesta."""
    out = document_out(doc, axes)
    return ReviewDocumentOut(
        seq=doc.seq,
        title=doc.title,
        folder=doc.folder,
        path=doc.path,
        domain_slug=doc.domain_slug,
        output_path=out.output_path,
        version=doc.version,
        version_group=doc.version_group,
        is_current=doc.is_current,
        axes=out.axes,
    )


IfMatch = Annotated[
    str | None,
    Header(description="``etag`` del manifiesto leído (``GET …/taxonomy-manifest``); obligatorio al cambiarlo"),
]
