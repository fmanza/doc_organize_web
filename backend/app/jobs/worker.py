"""Proceso worker (ADR-002): consume las colas de ``DOW_WORKER_QUEUES`` sobre la tabla ``runs``.

- Un subproceso ``multiprocessing`` *spawn* por job que recibe solo el ``run_id`` (``app.jobs.runner``). Este proceso
  **no importa doc_organize** (memoria): solo lo hacen los subprocesos.
- Latido de los runs y del propio worker; al arrancar cierra los runs huérfanos (latido caducado).
- Cancelación: el subproceso la atiende en un punto seguro; si no lo hace en ``DOW_CANCEL_GRACE_SECONDS`` se termina.
  Pasado ``DOW_JOB_TIMEOUT_SECONDS`` también se termina (``timeout``).
- Tareas periódicas en un hilo aparte (con varios workers solo uno las hace): sondeo de ubicaciones, purga del
  workspace y publicación de las capacidades del contenedor.

Uso::

    python -m app.jobs.worker
"""

from __future__ import annotations

import logging
import multiprocessing
import os
import signal
import socket
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from multiprocessing.process import BaseProcess
from typing import Final

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, sessionmaker

from app import __version__
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.models import FINISHED_RUN_STATUSES, Artifact, PeriodicTask, Run, RunEvent, Worker, utcnow
from app.db.session import get_engine
from app.domain.locations.service import probe_all
from app.domain.settings.service import effective_settings
from app.integrations.doc_organize import library_version, run_probe
from app.jobs import queue, runner
from app.workspace import runs as workspace

logger = logging.getLogger(__name__)

POLL_SECONDS: Final = 1.0
MAINTENANCE_SECONDS: Final = 30.0
KILL_AFTER_TERMINATE: Final = 5.0
CAPABILITIES_EVERY: Final = timedelta(hours=1)
PURGE_EVERY: Final = timedelta(hours=1)
ORPHANS_EVERY: Final = timedelta(minutes=1)
STALE_WORKER_ROWS: Final = timedelta(days=1)


@dataclass
class Slot:
    """Job en marcha en un subproceso."""

    run_id: str
    process: BaseProcess
    started: float = field(default_factory=time.monotonic)
    cancel_seen: float | None = None
    stop_reason: tuple[str, str | None, str | None] | None = None


class JobWorker:
    """Bucle principal del worker."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.id = f"{socket.gethostname()}:{os.getpid()}"
        self.queues = settings.queues
        self.factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
        self.slots: dict[str, Slot] = {}
        self.mp = multiprocessing.get_context("spawn")
        self._last_heartbeat = 0.0
        self._capabilities_running = threading.Lock()

    # --- ciclo de vida -----------------------------------------------------------------------------------------

    def register(self) -> None:
        """Da de alta el worker y cierra los runs huérfanos de una caída anterior."""
        with self.factory() as db:
            db.merge(
                Worker(
                    id=self.id,
                    queues=list(self.queues),
                    version=__version__,
                    doc_organize_version=library_version(),
                    started_at=utcnow(),
                    heartbeat_at=utcnow(),
                )
            )
            db.commit()
            orphans = queue.close_orphans(db, stale_before=self._stale_before(), worker_id=self.id)
        if orphans:
            logger.warning("Runs huérfanos cerrados", extra={"count": len(orphans)})
        logger.info("Worker iniciado", extra={"worker_id": self.id, "queues": list(self.queues)})

    def _stale_before(self) -> datetime:
        return utcnow() - timedelta(seconds=3 * self.settings.worker_heartbeat_seconds)

    def serve(self, stop: threading.Event) -> None:
        """Atiende las colas hasta que ``stop`` se active."""
        self.register()
        threading.Thread(target=self._maintenance, args=(stop,), name="dow-maintenance", daemon=True).start()
        self.refresh_capabilities()
        while not stop.is_set():
            self.tick()
            stop.wait(POLL_SECONDS)
        self.shutdown()

    def shutdown(self) -> None:
        """Termina los subprocesos en marcha (sus runs quedan ``failed``/``interrupted``) y se da de baja."""
        for slot in list(self.slots.values()):
            if slot.process.is_alive():
                slot.process.terminate()
                slot.process.join(KILL_AFTER_TERMINATE)
                if slot.process.is_alive():
                    slot.process.kill()
                    slot.process.join()
            with self.factory() as db:
                queue.finish(db, slot.run_id, "failed", code="interrupted", message="El worker se detuvo.")
        self.slots.clear()
        with self.factory() as db:
            db.execute(delete(Worker).where(Worker.id == self.id))
            db.commit()
        logger.info("Worker detenido", extra={"worker_id": self.id})

    # --- bucle -------------------------------------------------------------------------------------------------

    def tick(self) -> None:
        """Una vuelta: recoge terminados, vigila cancelaciones y timeouts, late y reclama trabajo nuevo."""
        self._reap()
        self._supervise()
        now = time.monotonic()
        if now - self._last_heartbeat >= self.settings.worker_heartbeat_seconds:
            self._heartbeat()
            self._last_heartbeat = now
        while len(self.slots) < self.settings.worker_concurrency:
            with self.factory() as db:
                run_id = queue.claim_next(db, self.id, self.queues)
            if run_id is None:
                break
            self._start(run_id)

    def _start(self, run_id: str) -> None:
        process = self.mp.Process(target=runner.main, args=(run_id,), name=f"dow-run-{run_id[:8]}")
        try:
            process.start()
        except OSError as exc:
            logger.error("No se pudo lanzar el subproceso", extra={"run_id": run_id, "exc_type": type(exc).__name__})
            with self.factory() as db:
                queue.finish(db, run_id, "failed", code="spawn_failed", message="No se pudo iniciar la operación.")
            return
        self.slots[run_id] = Slot(run_id=run_id, process=process)
        logger.info("Run lanzado", extra={"run_id": run_id, "pid": process.pid})

    def _reap(self) -> None:
        for run_id, slot in list(self.slots.items()):
            if slot.process.is_alive():
                continue
            slot.process.join()
            del self.slots[run_id]
            status, code, message = slot.stop_reason or (
                "failed",
                "crashed",
                "La operación terminó de forma inesperada.",
            )
            with self.factory() as db:
                # Si el subproceso cerró el run él mismo, ``finish`` no hace nada.
                if queue.finish(db, run_id, status, code=code, message=message):
                    logger.warning(
                        "Run cerrado por el worker",
                        extra={"run_id": run_id, "status": status, "exitcode": slot.process.exitcode},
                    )
                    register_log(db, self.settings, run_id)

    def _supervise(self) -> None:
        if not self.slots:
            return
        now = time.monotonic()
        with self.factory() as db:
            requested = queue.cancel_requested(db, list(self.slots))
        for run_id, slot in self.slots.items():
            if slot.stop_reason:
                if now - slot.started > 0 and slot.process.is_alive():
                    slot.process.kill()
                continue
            if now - slot.started > self.settings.job_timeout_seconds:
                self._stop(slot, ("failed", "timeout", "La operación superó el tiempo máximo."))
            elif run_id in requested:
                slot.cancel_seen = slot.cancel_seen or now
                if now - slot.cancel_seen > self.settings.cancel_grace_seconds:
                    self._stop(slot, ("cancelled", "cancel_forced", None))

    def _stop(self, slot: Slot, reason: tuple[str, str | None, str | None]) -> None:
        slot.stop_reason = reason
        slot.started = time.monotonic() + KILL_AFTER_TERMINATE  # plazo para ``kill`` si ignora ``terminate``
        slot.process.terminate()
        logger.warning("Subproceso terminado", extra={"run_id": slot.run_id, "reason": reason[1]})

    def _heartbeat(self) -> None:
        with self.factory() as db:
            queue.heartbeat(db, list(self.slots))
            worker = db.get(Worker, self.id)
            if worker is None:  # p. ej. borrado a mano: se vuelve a registrar
                db.merge(Worker(id=self.id, queues=list(self.queues), version=__version__, started_at=utcnow()))
                db.commit()
                return
            worker.heartbeat_at = utcnow()
            refresh = worker.refresh_requested
            worker.refresh_requested = False
            db.commit()
        if refresh:
            self.refresh_capabilities()

    # --- tareas en segundo plano -------------------------------------------------------------------------------

    def refresh_capabilities(self) -> None:
        """Sondea las capacidades del contenedor en un hilo (subproceso con torch) y las publica."""
        if not self._capabilities_running.acquire(blocking=False):
            return

        def _run() -> None:
            try:
                capabilities = asdict(run_probe())
            except RuntimeError as exc:
                logger.warning("Sondeo de capacidades fallido", extra={"exc_type": type(exc).__name__})
                return
            finally:
                self._capabilities_running.release()
            with self.factory() as db:
                db.execute(
                    update(Worker)
                    .where(Worker.id == self.id)
                    .values(capabilities=capabilities, capabilities_at=utcnow())
                )
                db.commit()

        threading.Thread(target=_run, name="dow-capabilities", daemon=True).start()

    def _maintenance(self, stop: threading.Event) -> None:
        while not stop.wait(MAINTENANCE_SECONDS):
            try:
                self.maintenance_once()
            except Exception as exc:  # noqa: BLE001 - el hilo no debe morir por un fallo puntual
                logger.error("Tarea periódica fallida", extra={"exc_type": type(exc).__name__})

    def maintenance_once(self) -> None:
        """Sondeo de ubicaciones, purga del workspace, capacidades y limpieza de workers caídos, si les toca."""
        with self.factory() as db:
            settings = effective_settings(db, self.settings)
            interval = settings.location_probe_interval_minutes
            if interval and queue.claim_periodic(db, "probe_locations", self.id, timedelta(minutes=interval)):
                logger.info("Ubicaciones sondeadas", extra={"statuses": probe_all(db, settings)})
            if queue.claim_periodic(db, "purge_workspace", self.id, PURGE_EVERY):
                purge_workspace(db, settings)
            if queue.claim_periodic(db, "close_orphans", self.id, ORPHANS_EVERY):
                # Runs de workers que murieron sin que nadie los reiniciara (varios workers, o uno que no vuelve).
                for run_id in queue.close_orphans(db, stale_before=self._stale_before()):
                    logger.warning("Run huérfano cerrado", extra={"run_id": run_id})
            if queue.claim_periodic(db, f"capabilities:{self.id}", self.id, CAPABILITIES_EVERY):
                self.refresh_capabilities()
            gone = list(db.scalars(select(Worker.id).where(Worker.heartbeat_at < utcnow() - STALE_WORKER_ROWS)))
            if gone:
                db.execute(delete(Worker).where(Worker.id.in_(gone)))
                db.execute(delete(PeriodicTask).where(PeriodicTask.name.in_([f"capabilities:{w}" for w in gone])))
            db.commit()


def register_log(db: Session, settings: Settings, run_id: str) -> None:
    """Registra ``logs/run.log`` como artefacto si el subproceso no llegó a hacerlo (timeout, *kill*, caída)."""
    if db.scalar(select(Artifact.id).where(Artifact.run_id == run_id, Artifact.kind == "log")) is not None:
        return
    path = workspace.artifact_path(settings, run_id, workspace.LOG_REL)
    if path is None:
        return
    created_by = db.scalar(select(Run.created_by).where(Run.id == run_id))
    db.add(
        Artifact(
            run_id=run_id,
            name="run.log",
            kind="log",
            rel_path=workspace.LOG_REL,
            size_bytes=path.stat().st_size,
            content_type="text/plain",
            created_by=created_by,
        )
    )
    db.commit()


def purge_workspace(db: Session, settings: Settings) -> int:
    """Borra las carpetas de runs terminados hace más de ``run_retention_days`` y sus eventos de progreso y avisos.

    Se conservan la fila del run (historial), sus artefactos (para responder 410) y sus eventos de estado.
    """
    limit = utcnow() - timedelta(days=settings.run_retention_days)
    expired = list(
        db.scalars(
            select(Run.id).where(
                Run.status.in_(FINISHED_RUN_STATUSES), Run.finished_at < limit, Run.workspace_purged_at.is_(None)
            )
        )
    )
    for run_id in expired:
        workspace.purge(settings, run_id)
        db.execute(update(Run).where(Run.id == run_id).values(workspace_purged_at=utcnow()))
        db.execute(delete(RunEvent).where(RunEvent.run_id == run_id, RunEvent.type.in_(("progress", "log"))))
        db.commit()
    if expired:
        logger.info("Workspace purgado", extra={"runs": len(expired)})
    return len(expired)


def main() -> int:
    settings = get_settings()
    configure_logging(settings.log_level)
    stop = threading.Event()

    def _handle(signum: int, _: object) -> None:
        logger.info("Señal recibida", extra={"signal": signal.Signals(signum).name})
        stop.set()

    signal.signal(signal.SIGTERM, _handle)
    signal.signal(signal.SIGINT, _handle)
    JobWorker(settings).serve(stop)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
