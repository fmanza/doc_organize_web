"""Consulta de los errores de conversión guardados por los runs ``scan`` (WB-4.3), paginada en servidor."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import FINISHED_RUN_STATUSES, Run, ScanError
from app.domain.listing import ListQuery, apply_search, apply_sort


def run_errors(
    db: Session, run_id: str, *, limit: int, offset: int, listing: ListQuery | None = None
) -> tuple[list[ScanError], int]:
    """Errores de un run (por ruta si no se pide otro orden), filtrados por texto en la ruta o el mensaje."""
    listing = listing or ListQuery()
    query = apply_search(
        select(ScanError).where(ScanError.run_id == run_id), listing.q, [ScanError.path, ScanError.message]
    )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    columns = {"path": ScanError.path, "message": func.lower(ScanError.message), "retry_count": ScanError.retry_count}
    query = apply_sort(query, listing, columns, default=[ScanError.path], tiebreak=ScanError.id)
    rows = db.scalars(query.limit(limit).offset(offset)).all()
    return list(rows), total


def last_scan(db: Session, project_id: int) -> Run | None:
    """Último escaneo real terminado del proyecto (sin vistas previas)."""
    query = (
        select(Run)
        .where(
            Run.project_id == project_id,
            Run.operation == "scan",
            Run.is_write.is_(True),
            Run.status.in_(FINISHED_RUN_STATUSES),
        )
        .order_by(Run.finished_at.desc(), Run.created_at.desc())
        .limit(1)
    )
    return db.scalars(query).unique().first()
