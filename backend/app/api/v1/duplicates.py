"""Duplicados (Fase 6): grupos de una vista previa y última aplicación del proyecto.

Lanzar la vista previa (``dedup_preview``) y aplicar (``dedup_apply``) son runs: ``POST /projects/{id}/runs``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.api.v1.listing import GroupSort, OrderQuery, SearchQuery, listing
from app.api.v1.schemas import (
    MAX_PAGE_SIZE,
    DuplicateGroupOut,
    DuplicateGroupPage,
    DuplicateMemberOut,
    DuplicatesLastOut,
    RunBrief,
)
from app.db.models import DuplicateGroupRow
from app.domain.documents.outputs import output_paths
from app.domain.duplicates import service as duplicates
from app.domain.duplicates.service import member_key
from app.domain.projects import service as projects
from app.domain.runs import service as runs

router = APIRouter(tags=["duplicates"])

_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"description": "No autenticado"},
    404: {"description": "No encontrado (o sin acceso)"},
}


def _group_out(row: DuplicateGroupRow) -> DuplicateGroupOut:
    return DuplicateGroupOut(
        group_id=row.group_id,
        reason=row.reason,
        members=[
            DuplicateMemberOut(
                key=member_key(m),
                folder=m["folder"],
                path=m["path"],
                size_bytes=m["size_bytes"],
                modified_at=datetime.fromtimestamp(float(m["modified_time"]), UTC),
                sha256=m["sha256"],
                canonical=m["canonical"],
                output_path=output_paths(m["folder"], m["path"]).markdown,
            )
            for m in row.members
        ],
    )


@router.get(
    "/runs/{run_id}/duplicate-groups",
    response_model=DuplicateGroupPage,
    summary="Grupos de una búsqueda de duplicados",
    responses=_ERRORS,
)
def list_duplicate_groups(
    run_id: str,
    user: CurrentUser,
    db: DbSession,
    reason: Annotated[
        Literal["exact_duplicate", "version_conflict", "fuzzy_name_match"] | None, Query(description="Solo este motivo")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    q: SearchQuery = None,
    sort: Annotated[GroupSort | None, Query(description="Columna por la que ordenar")] = None,
    order: OrderQuery = "asc",
) -> DuplicateGroupPage:
    """Grupos de la vista previa ``run_id`` (vacío si el run no es una búsqueda de duplicados)."""
    run, _ = runs.get_run(db, run_id, user)
    rows, total = duplicates.list_groups(
        db, run.id, reason=reason, limit=limit, offset=offset, listing=listing(q, sort, order)
    )
    return DuplicateGroupPage(run=RunBrief.model_validate(run), items=[_group_out(r) for r in rows], total=total)


@router.get(
    "/projects/{project_id}/duplicates/last",
    response_model=DuplicatesLastOut,
    summary="Última búsqueda y aplicación de duplicados",
    responses=_ERRORS,
)
def last_duplicates(project_id: int, user: CurrentUser, db: DbSession) -> DuplicatesLastOut:
    """Para el aviso «la última aplicación ya resolvió los duplicados» del resolutor."""
    access = projects.get_access(db, project_id, user)
    last = duplicates.last_runs(db, access.project.id)
    return DuplicatesLastOut(
        preview=RunBrief.model_validate(last.preview) if last.preview else None,
        apply=RunBrief.model_validate(last.apply) if last.apply else None,
    )
