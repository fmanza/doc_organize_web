"""Calidad de la clasificación (W5): métricas y conjunto de referencia («gold»)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Request, status
from pydantic import StringConstraints

from app.api.deps import Context, CurrentUser, DbSession, SettingsDep
from app.api.v1.context._shared import ERRORS
from app.api.v1.schemas import (
    GoldOut,
    QualityOut,
    QualityRunOut,
)
from app.core.errors import AppError
from app.domain.context import decisions as decisions_service
from app.domain.context import quality
from app.domain.projects import service as projects

router = APIRouter(tags=["context"])


def _gold_out(gold: quality.Gold | None) -> GoldOut | None:
    return GoldOut.model_validate(gold.__dict__) if gold else None


def _latest(db: DbSession, project_id: int, operation: str) -> QualityRunOut | None:
    from sqlalchemy import select

    from app.db.models import Run

    run = db.scalar(
        select(Run)
        .where(Run.project_id == project_id, Run.operation == operation, Run.status == "succeeded")
        .order_by(Run.finished_at.desc())
        .limit(1)
    )
    if run is None or not isinstance(run.result, dict):
        return None
    return QualityRunOut(run_id=run.id, finished_at=run.finished_at, result=run.result)


@router.get(
    "/projects/{project_id}/context/quality",
    response_model=QualityOut,
    summary="Calidad de la clasificación",
    responses=ERRORS,
)
def get_quality(project_id: int, user: CurrentUser, db: DbSession, settings: SettingsDep) -> QualityOut:
    """La referencia subida, si hay decisiones con las que hacer una, y la última evaluación y comparación terminadas
    (``context_evaluate`` y ``context_dry_run``)."""
    access = projects.get_access(db, project_id, user)
    try:
        decisions = bool(decisions_service.load(db, settings, access.project).active)
    except AppError:  # informativo: sin destino, sin contexto o carpeta sustituida, no hay decisiones que usar
        decisions = False
    return QualityOut(
        gold=_gold_out(quality.read_gold(settings, access.project)),
        decisions_available=decisions,
        evaluation=_latest(db, project_id, "context_evaluate"),
        dry_run=_latest(db, project_id, "context_dry_run"),
        audit=_latest(db, project_id, "context_audit"),
    )


@router.put(
    "/projects/{project_id}/context/quality/gold",
    response_model=GoldOut,
    summary="Subir la referencia en Excel",
    responses={**ERRORS, 403: {"description": "Rol insuficiente (editor)"}, 422: {"description": "gold_invalid"}},
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}},
        }
    },
)
async def put_gold(
    project_id: int,
    request: Request,
    user: CurrentUser,
    db: DbSession,
    settings: SettingsDep,
    ctx: Context,
    filename: Annotated[str, Query(min_length=1, max_length=255)] = "referencia.xlsx",
    sheet: Annotated[str, Query(min_length=1, max_length=100)] = "Referencia",
    document_column: Annotated[str, Query(min_length=1, max_length=100)] = "documento",
    columns: Annotated[
        list[Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,40}:[^:]{1,100}$")]] | None,
        Query(
            max_length=10,
            description="Eje y columna, ``eje:columna`` (repetible); sin ninguno, ``dominio_ok`` y ``tipo_ok``",
        ),
    ] = None,
) -> GoldOut:
    """Referencia etiquetada a mano (``.xlsx``, como mucho 5 MB): una fila por documento con su clave
    (``<carpeta>/<ruta>``) y, por eje, el valor correcto (varios separados por coma; ``ninguno`` si ninguno). Se
    comprueba con ``load_gold_xlsx`` y sustituye a la anterior; propietario o editor, auditado sin el contenido."""
    access = projects.get_access(db, project_id, user, min_role="editor")
    body = await request.body()
    mapping = dict(item.split(":", 1) for item in columns or [])
    gold = quality.upload_gold(
        db,
        settings,
        access.project,
        body,
        filename=filename,
        sheet=sheet,
        document_column=document_column,
        columns=mapping,
        actor=user,
        ctx=ctx,
    )
    return GoldOut.model_validate(gold.__dict__)


@router.delete(
    "/projects/{project_id}/context/quality/gold",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Borrar la referencia en Excel",
    responses={**ERRORS, 403: {"description": "Rol insuficiente (editor)"}},
)
def delete_gold(project_id: int, user: CurrentUser, db: DbSession, settings: SettingsDep, ctx: Context) -> None:
    """Borra la referencia subida."""
    access = projects.get_access(db, project_id, user, min_role="editor")
    quality.delete_gold(db, settings, access.project, actor=user, ctx=ctx)
