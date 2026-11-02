"""``/api/v1/projects/{id}/documents``, ``/outputs`` y ``/search``: caché, visor de salidas y búsqueda (Fase 5).

Solo lectura y para cualquier miembro del proyecto. Las exportaciones son runs (``POST /projects/{id}/runs``).
"""

from __future__ import annotations

from typing import Annotated, Any, Literal
from urllib.parse import quote

from fastapi import APIRouter, Query
from fastapi.responses import Response

from app.api.deps import CurrentUser, DbSession, SettingsDep
from app.api.v1.schemas import MAX_PAGE_SIZE, DocumentOut, DocumentPage, SearchHitOut, SearchPage
from app.domain.documents import service as documents
from app.domain.projects import service as projects
from app.domain.projects.service import state_dir
from app.domain.search.index import search, search_db

router = APIRouter(prefix="/projects", tags=["documents"])

#: ``ConversionStatus`` de doc_organize (filtro de la lista, G22).
ConversionFilter = Literal["pending", "in_progress", "success", "error", "ocr_pending", "ocr_in_progress"]

_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"description": "No autenticado"},
    404: {"description": "Proyecto no encontrado (o sin acceso)"},
}


@router.get(
    "/{project_id}/documents",
    response_model=DocumentPage,
    summary="Documentos del proyecto",
    responses={**_ERRORS, 422: {"description": "La carpeta no es de origen del proyecto (folder_not_saved)"}},
)
def list_documents(
    project_id: int,
    user: CurrentUser,
    db: DbSession,
    settings: SettingsDep,
    search_text: Annotated[
        str | None,
        Query(
            alias="search",
            max_length=200,
            description="Texto en la ruta relativa a la carpeta (sin distinguir mayúsculas)",
        ),
    ] = None,
    folder: Annotated[str | None, Query(max_length=4096, description="Solo esta carpeta de origen")] = None,
    conversion_status: Annotated[
        ConversionFilter | None, Query(description="Solo documentos con este estado de conversión")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DocumentPage:
    """Documentos de la caché de doc_organize, por carpeta de origen y ruta, con su estado de conversión. La búsqueda
    mira la ruta relativa a la carpeta, nunca la del servidor."""
    access = projects.get_access(db, project_id, user)
    rows, total = documents.list_documents(
        settings,
        access.project,
        folder=folder,
        search=search_text,
        conversion_status=conversion_status,
        limit=limit,
        offset=offset,
    )
    return DocumentPage(items=[DocumentOut.model_validate(row) for row in rows], total=total)


@router.get(
    "/{project_id}/outputs",
    response_class=Response,
    summary="Ver una salida convertida",
    responses={
        **_ERRORS,
        400: {"description": "Ruta no válida"},
        413: {"description": "Demasiado grande para el visor (output_too_large)"},
        415: {"description": "Tipo no permitido en el visor (output_type_not_allowed)"},
        503: {"description": "Ubicación no disponible"},
    },
)
def get_output(
    project_id: int,
    user: CurrentUser,
    db: DbSession,
    settings: SettingsDep,
    path: Annotated[str, Query(max_length=4096, description="Fichero relativo a Conversión/ del proyecto")],
) -> Any:
    """Markdown, JSON o imagen de ``Conversión/`` con tipo fijo; el navegador nunca lo interpreta como página."""
    access = projects.get_access(db, project_id, user)
    output = documents.read_output(settings, access.project, path)
    return Response(
        content=output.content,
        media_type=output.content_type,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
            "Content-Security-Policy": "default-src 'none'; sandbox; frame-ancestors 'none'",
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(output.name)}",
        },
    )


@router.get(
    "/{project_id}/search",
    response_model=SearchPage,
    summary="Buscar en el contenido",
    responses={
        **_ERRORS,
        422: {"description": "Texto vacío o demasiado largo, demasiado amplio (search_too_broad) o carpeta ajena"},
    },
)
def search_content(
    project_id: int,
    user: CurrentUser,
    db: DbSession,
    settings: SettingsDep,
    q: Annotated[str, Query(min_length=1, max_length=200, description="Palabras a buscar (todas)")],
    folder: Annotated[str | None, Query(max_length=4096, description="Solo esta carpeta de origen")] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SearchPage:
    """Documentos convertidos que contienen todas las palabras, los más relevantes primero."""
    access = projects.get_access(db, project_id, user)
    hits, total, indexed_at = search(
        search_db(state_dir(settings, access.project.id)),
        q,
        folders=documents.select_folders(access.project, folder),
        limit=limit,
        offset=offset,
    )
    return SearchPage(items=[SearchHitOut.model_validate(h) for h in hits], total=total, indexed_at=indexed_at)
