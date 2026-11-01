"""Workers vistos desde la API: vivos o caídos, capacidades publicadas y petición de refresco.

Un worker está **vivo** si su latido es más reciente que 3× ``worker_heartbeat_seconds``. Las capacidades de la
instancia son las del worker vivo más reciente de la cola ``cpu`` (o de cualquiera, si no hay de ``cpu``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import User, Worker, utcnow
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction, RequestContext

WorkerHealth = Literal["none", "ok", "stale"]


def _alive_since(settings: Settings) -> datetime:
    return utcnow() - timedelta(seconds=3 * settings.worker_heartbeat_seconds)


def list_workers(db: Session) -> list[Worker]:
    """Workers registrados, el latido más reciente primero."""
    return list(db.scalars(select(Worker).order_by(Worker.heartbeat_at.desc())))


def is_alive(worker: Worker, settings: Settings) -> bool:
    """Si el latido del worker es reciente."""
    return worker.heartbeat_at >= _alive_since(settings)


def health(db: Session, settings: Settings) -> WorkerHealth:
    """``ok`` si hay algún worker vivo, ``stale`` si solo hay caídos y ``none`` si no hay ninguno."""
    workers = list_workers(db)
    if not workers:
        return "none"
    return "ok" if any(is_alive(w, settings) for w in workers) else "stale"


@dataclass(frozen=True)
class CapabilitiesView:
    """Capacidades publicadas por un worker.

    Attributes:
        status: ``ok`` si hay datos de un worker vivo; ``pending`` si el worker vivo aún no las publicó; ``no_worker``
            si no hay worker vivo (se devuelven las últimas conocidas, si las hay).
        checked_at: Cuándo se obtuvieron.
        capabilities: Datos del sondeo.
        queues: Colas con algún worker vivo.
    """

    status: Literal["ok", "pending", "no_worker"]
    checked_at: datetime | None
    capabilities: dict[str, Any] | None
    queues: list[str]


def capabilities(db: Session, settings: Settings) -> CapabilitiesView:
    """Capacidades de la instancia según los workers."""
    workers = list_workers(db)
    alive = [w for w in workers if is_alive(w, settings)]
    queues = sorted({q for w in alive for q in w.queues})
    candidates = sorted(alive, key=lambda w: ("cpu" not in w.queues, -(w.capabilities_at or w.started_at).timestamp()))
    for worker in candidates:
        if worker.capabilities is not None:
            return CapabilitiesView("ok", worker.capabilities_at, worker.capabilities, queues)
    if alive:
        return CapabilitiesView("pending", None, None, queues)
    known = [w for w in workers if w.capabilities is not None]
    if known:
        return CapabilitiesView("no_worker", known[0].capabilities_at, known[0].capabilities, [])
    return CapabilitiesView("no_worker", None, None, [])


def request_refresh(db: Session, *, actor: User, ctx: RequestContext) -> int:
    """Pide a los workers vivos que vuelvan a sondear sus capacidades; devuelve cuántos lo harán."""
    since = utcnow() - timedelta(minutes=5)
    count = db.execute(update(Worker).where(Worker.heartbeat_at >= since).values(refresh_requested=True)).rowcount  # type: ignore[attr-defined]
    audit.record(
        db,
        action=AuditAction.WORKER_CAPABILITIES_REFRESH,
        ctx=ctx,
        actor_id=actor.id,
        target_type="worker",
        details={"workers": count},
    )
    db.commit()
    return int(count)
