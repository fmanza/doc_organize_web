"""Cola sobre la tabla ``runs`` (ADR-002): reclamo atómico, latido, huérfanos y cierre de runs.

El reclamo es el **único SQL crudo** de la aplicación (``UPDATE … RETURNING``, SQLite ≥ 3.35 y PostgreSQL): dos
workers nunca reclaman el mismo run. El resto usa el ORM.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Final

from sqlalchemy import bindparam, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import PeriodicTask, Run, UTCDateTime, utcnow
from app.domain.runs import events

_CLAIM: Final = text(
    """
    UPDATE runs
       SET status = 'running', worker_id = :worker_id, started_at = :now, heartbeat_at = :now
     WHERE id = (SELECT id FROM runs
                  WHERE status = 'queued' AND queue IN :queues
                  ORDER BY created_at, id
                  LIMIT 1)
       AND status = 'queued'
    RETURNING id
    """
).bindparams(bindparam("queues", expanding=True), bindparam("now", type_=UTCDateTime()))


def claim_next(db: Session, worker_id: str, queues: tuple[str, ...]) -> str | None:
    """Reclama el run en cola más antiguo de ``queues`` y emite su evento ``running``; ``None`` si no hay."""
    run_id = db.execute(_CLAIM, {"worker_id": worker_id, "now": utcnow(), "queues": list(queues)}).scalar()
    db.commit()
    if run_id is not None:
        events.append(db, run_id, "status", {"status": "running"})
    return run_id


def heartbeat(db: Session, run_ids: list[str]) -> None:
    """Actualiza el latido de los runs en marcha de este worker."""
    if run_ids:
        db.execute(update(Run).where(Run.id.in_(run_ids), Run.status == "running").values(heartbeat_at=utcnow()))
        db.commit()


def cancel_requested(db: Session, run_ids: list[str]) -> set[str]:
    """Runs de ``run_ids`` con cancelación pedida que se pueden interrumpir (fuera de una fase crítica)."""
    if not run_ids:
        return set()
    query = select(Run.id).where(Run.id.in_(run_ids), Run.cancel_requested.is_(True), Run.uninterruptible.is_(False))
    return set(db.scalars(query))


def finish(db: Session, run_id: str, status: str, *, code: str | None = None, message: str | None = None) -> bool:
    """Cierra un run en marcha con ``status`` y emite ``status`` + ``end``; ``False`` si ya estaba cerrado.

    Condicional (``WHERE status = 'running'``): si el subproceso ya lo cerró, el worker no lo pisa. El cambio de estado
    y sus eventos ``status`` + ``end`` se confirman juntos: el SSE nunca ve un run cerrado sin ``end``.
    """
    data = {"status": status, **({"error_code": code} if code else {})}
    for _ in range(5):
        closed = db.execute(
            update(Run)
            .where(Run.id == run_id, Run.status == "running")
            .values(status=status, finished_at=utcnow(), error_code=code, error_message=message, uninterruptible=False)
        ).rowcount  # type: ignore[attr-defined]
        if not closed:
            db.rollback()
            return False
        events.stage(db, run_id, [("status", data), ("end", data)])
        try:
            db.commit()
        except IntegrityError:  # otro proceso añadió un evento con el mismo ``seq``: se repite
            db.rollback()
            continue
        return True
    raise RuntimeError("No se pudo cerrar el run")


def close_orphans(db: Session, *, stale_before: datetime, worker_id: str | None = None) -> list[str]:
    """Marca ``failed`` (``orphaned``) los runs en marcha cuyo latido es anterior a ``stale_before`` y, con
    ``worker_id``, todos los de ese worker (una encarnación anterior con el mismo ``hostname:pid``, p. ej. tras un
    reinicio del contenedor más rápido que el latido)."""
    stale = (Run.heartbeat_at.is_(None)) | (Run.heartbeat_at < stale_before)
    if worker_id is not None:
        stale = stale | (Run.worker_id == worker_id)
    orphans = list(db.scalars(select(Run.id).where(Run.status == "running", stale)))
    for run_id in orphans:
        finish(db, run_id, "failed", code="orphaned", message="El worker que ejecutaba la operación dejó de responder.")
    return orphans


def claim_periodic(db: Session, name: str, worker_id: str, interval: timedelta) -> bool:
    """Reclama la tarea periódica ``name`` si toca; con varios workers solo uno la ejecuta en cada intervalo."""
    if db.get(PeriodicTask, name) is None:
        db.add(PeriodicTask(name=name))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
    now = utcnow()
    claimed = db.execute(
        update(PeriodicTask)
        .where(
            PeriodicTask.name == name,
            (PeriodicTask.last_run_at.is_(None)) | (PeriodicTask.last_run_at <= now - interval),
        )
        .values(last_run_at=now, claimed_by=worker_id)
    ).rowcount  # type: ignore[attr-defined]
    db.commit()
    return bool(claimed)
