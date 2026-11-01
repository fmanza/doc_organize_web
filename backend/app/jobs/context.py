"""Contexto que recibe una operación dentro del subproceso de su job.

Da acceso a los parámetros, a la carpeta del run y a las acciones que el usuario ve: progreso (limitado a uno por
segundo), avisos, artefactos y la cancelación cooperativa (un hilo consulta ``runs.cancel_requested`` cada pocos
segundos).
"""

from __future__ import annotations

import mimetypes
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Artifact, ArtifactKind, Run
from app.domain.runs import events

PROGRESS_MIN_INTERVAL: Final = 1.0
CANCEL_POLL_SECONDS: Final = 2.0


class JobCancelled(Exception):
    """El usuario pidió cancelar y la operación paró en un punto seguro."""


class JobFailed(Exception):
    """Fallo esperado de una operación, con código y mensaje aptos para el usuario (sin rutas del contenedor)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class JobContext:
    """Estado de un job en marcha.

    Attributes:
        run_id: Run que se ejecuta.
        settings: Ajustes efectivos (con los administrables) al empezar el job.
        session_factory: Fábrica de sesiones de ``config.db``.
        workdir: Carpeta del run en el workspace.
        created_by: Usuario que lanzó el run (dueño de sus artefactos).
    """

    run_id: str
    settings: Settings
    session_factory: Callable[[], Session]
    workdir: Path
    created_by: int | None
    _cancel: threading.Event = field(default_factory=threading.Event)
    _last_progress: float = 0.0
    _last_phase: str | None = None
    _stop: threading.Event = field(default_factory=threading.Event)

    # --- cancelación -------------------------------------------------------------------------------------------

    def start_cancel_watch(self) -> None:
        """Arranca el hilo que vigila ``cancel_requested``."""
        threading.Thread(target=self._watch_cancel, name="dow-cancel-watch", daemon=True).start()

    def stop_cancel_watch(self) -> None:
        """Para el hilo de vigilancia."""
        self._stop.set()

    def _watch_cancel(self) -> None:
        while not self._stop.wait(CANCEL_POLL_SECONDS):
            with self.session_factory() as db:
                if db.scalar(select(Run.cancel_requested).where(Run.id == self.run_id)):
                    self._cancel.set()
                    return

    @property
    def cancelled(self) -> bool:
        """Si se ha pedido cancelar (puente para el ``CancelToken`` de doc_organize, G2)."""
        return self._cancel.is_set()

    def check_cancelled(self) -> None:
        """Punto seguro de parada.

        Raises:
            JobCancelled: Se pidió cancelar.
        """
        if self._cancel.is_set():
            raise JobCancelled()

    @contextmanager
    def uninterruptible(self) -> Iterator[None]:
        """Fase crítica (borrar, mover): el worker no termina el subproceso por una cancelación mientras dure.

        Una cancelación pedida durante la fase se atiende después, en el siguiente ``check_cancelled``; el timeout del
        job sigue aplicando (límite duro).
        """
        self._set_uninterruptible(True)
        try:
            yield
        finally:
            self._set_uninterruptible(False)

    def _set_uninterruptible(self, value: bool) -> None:
        with self.session_factory() as db:
            db.execute(update(Run).where(Run.id == self.run_id).values(uninterruptible=value))
            db.commit()

    # --- lo que ve el usuario ----------------------------------------------------------------------------------

    def progress(self, phase: str, processed: int, total: int | None = None, current: str | None = None) -> None:
        """Publica el progreso: como mucho uno por segundo, salvo al cambiar de fase o al terminarla."""
        now = time.monotonic()
        finished = total is not None and processed >= total
        if phase == self._last_phase and not finished and now - self._last_progress < PROGRESS_MIN_INTERVAL:
            return
        self._last_progress, self._last_phase = now, phase
        data: dict[str, Any] = {"phase": phase, "processed": processed, "total": total, "current": current}
        with self.session_factory() as db:
            db.execute(update(Run).where(Run.id == self.run_id).values(progress=data))
            db.commit()
            events.append(db, self.run_id, "progress", data)

    def log(self, message: str, *, level: str = "info") -> None:
        """Aviso para el usuario en el detalle del run (sin rutas del contenedor ni texto de excepciones)."""
        with self.session_factory() as db:
            events.append(db, self.run_id, "log", {"level": level, "message": message})

    def add_artifact(self, rel_path: str, *, name: str | None = None, kind: ArtifactKind = "output") -> None:
        """Registra un fichero de la carpeta del run como artefacto descargable."""
        path = (self.workdir / rel_path).resolve()
        if not path.is_relative_to(self.workdir.resolve()) or not path.is_file():
            raise ValueError("El artefacto debe ser un fichero de la carpeta del run")
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        with self.session_factory() as db:
            artifact = Artifact(
                run_id=self.run_id,
                name=name or path.name,
                kind=kind,
                rel_path=path.relative_to(self.workdir.resolve()).as_posix(),
                size_bytes=path.stat().st_size,
                content_type=content_type,
                created_by=self.created_by,
            )
            db.add(artifact)
            db.commit()
            events.append(
                db,
                self.run_id,
                "artifact",
                {"id": artifact.id, "name": artifact.name, "kind": kind, "size_bytes": artifact.size_bytes},
            )
