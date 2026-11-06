"""Workers vistos desde la API: vivos o caídos, capacidades publicadas y petición de refresco.

Un worker está **vivo** si su latido es más reciente que 3× ``worker_heartbeat_seconds``. Las capacidades de la
instancia suman las de los workers vivos: una capacidad está si algún worker la tiene, y se dice en qué colas (1.0.1:
antes solo se miraba el worker de ``cpu`` y la ficha decía «No» a la GPU de un ``worker-gpu``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Literal

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Run, User, Worker, utcnow
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction, RequestContext

WorkerHealth = Literal["none", "ok", "stale"]


def _alive_since(settings: Settings) -> datetime:
    return utcnow() - timedelta(seconds=3 * settings.worker_heartbeat_seconds)


def list_workers(db: Session) -> list[Worker]:
    """Workers registrados, el latido más reciente primero."""
    return list(db.scalars(select(Worker).order_by(Worker.heartbeat_at.desc())))


def running_by_worker(db: Session) -> dict[str, int]:
    """Ejecuciones ``running`` por ``worker_id`` (las que cada worker tiene en marcha ahora)."""
    rows = db.execute(
        select(Run.worker_id, func.count())
        .where(Run.status == "running", Run.worker_id.is_not(None))
        .group_by(Run.worker_id)
    )
    return {str(worker_id): int(count) for worker_id, count in rows}


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
        capability_queues: Por cada capacidad booleana que algún worker vivo tiene, las colas de esos workers.
    """

    status: Literal["ok", "pending", "no_worker"]
    checked_at: datetime | None
    capabilities: dict[str, Any] | None
    queues: list[str]
    capability_queues: dict[str, list[str]] = field(default_factory=dict)


def _merge(published: list[Worker]) -> tuple[dict[str, Any], dict[str, list[str]]]:
    """Suma las capacidades de ``published`` (el primero manda en los valores que no son booleanos): un booleano es
    verdadero si lo es en algún worker, y se anotan las colas de los workers que lo tienen."""
    merged: dict[str, Any] = {}
    queues: dict[str, set[str]] = {}
    for worker in published:
        for key, value in (worker.capabilities or {}).items():
            if isinstance(value, bool):
                merged[key] = merged.get(key, False) or value
                if value:
                    queues.setdefault(key, set()).update(worker.queues)
            else:
                merged.setdefault(key, value)
    return merged, {key: sorted(found) for key, found in sorted(queues.items())}


def capabilities(db: Session, settings: Settings) -> CapabilitiesView:
    """Capacidades de la instancia: la suma de las de los workers vivos (``checked_at``, la comprobación más antigua)."""
    workers = list_workers(db)
    alive = [w for w in workers if is_alive(w, settings)]
    queues = sorted({q for w in alive for q in w.queues})
    published = sorted(
        (w for w in alive if w.capabilities is not None),
        key=lambda w: ("cpu" not in w.queues, -(w.capabilities_at or w.started_at).timestamp()),
    )
    if published:
        merged, by_queue = _merge(published)
        checked = [w.capabilities_at for w in published if w.capabilities_at is not None]
        return CapabilitiesView("ok", min(checked) if checked else None, merged, queues, by_queue)
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
