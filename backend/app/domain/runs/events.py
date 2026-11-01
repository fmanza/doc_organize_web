"""Eventos de un run (fuente del SSE, ADR-008).

Cada evento tiene un ``seq`` creciente por run, que es su ``id`` en el SSE (reanudación con ``Last-Event-ID``). Tipos:

- ``status``: cambio de estado (``queued``, ``running``, ``succeeded``, ``failed``, ``cancelled``).
- ``progress``: fase, procesados, total y elemento actual (persistido como mucho una vez por segundo).
- ``log``: aviso para el usuario (nunca rutas del contenedor ni texto de excepciones de terceros).
- ``artifact``: fichero nuevo en el workspace del run.
- ``end``: último evento; el SSE se cierra tras enviarlo.

Todos llevan ``schema_version`` para que el cliente detecte cambios de formato.
"""

from __future__ import annotations

from typing import Any, Final, Literal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import RunEvent

EVENT_SCHEMA_VERSION: Final = 1
EventType = Literal["status", "progress", "log", "artifact", "end"]
_RETRIES: Final = 5


def append(db: Session, run_id: str, type_: EventType, data: dict[str, Any]) -> RunEvent:
    """Añade un evento y confirma la transacción.

    La API (cancelar) y el subproceso del job pueden escribir a la vez: si dos calculan el mismo ``seq``, el segundo
    choca con la clave primaria y reintenta.
    """
    payload = {"schema_version": EVENT_SCHEMA_VERSION, **data}
    for attempt in range(_RETRIES):
        seq = (db.scalar(select(func.max(RunEvent.seq)).where(RunEvent.run_id == run_id)) or 0) + 1
        event = RunEvent(run_id=run_id, seq=seq, type=type_, data=payload)
        db.add(event)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            if attempt == _RETRIES - 1:
                raise
            continue
        return event
    raise AssertionError("inalcanzable")  # pragma: no cover


def stage(db: Session, run_id: str, items: list[tuple[EventType, dict[str, Any]]]) -> None:
    """Añade eventos a la transacción en curso **sin confirmarla** (quien llama confirma y reintenta si choca el
    ``seq``)."""
    seq = db.scalar(select(func.max(RunEvent.seq)).where(RunEvent.run_id == run_id)) or 0
    for offset, (type_, data) in enumerate(items, start=1):
        payload = {"schema_version": EVENT_SCHEMA_VERSION, **data}
        db.add(RunEvent(run_id=run_id, seq=seq + offset, type=type_, data=payload))


def after(db: Session, run_id: str, last_seq: int, *, limit: int = 500) -> list[RunEvent]:
    """Eventos de ``run_id`` posteriores a ``last_seq``, en orden."""
    query = (
        select(RunEvent).where(RunEvent.run_id == run_id, RunEvent.seq > last_seq).order_by(RunEvent.seq).limit(limit)
    )
    return list(db.scalars(query))
