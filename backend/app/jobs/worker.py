"""Proceso worker (esqueleto de la Fase 0).

En la Fase 3 consumirá las colas ``cpu``/``gpu`` sobre la tabla ``runs`` (ADR-002). De momento solo arranca, registra
los volúmenes compartidos con la API y espera a ``SIGTERM``/``SIGINT`` para terminar de forma limpia.

Uso::

    python -m app.jobs.worker
"""

from __future__ import annotations

import logging
import signal

from app.core.config import get_settings
from app.core.logging import configure_logging

logger = logging.getLogger(__name__)


def main() -> int:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger.info(
        "Worker iniciado sin operaciones registradas (Fase 3)",
        extra={"data_dir": str(settings.data_dir), "workspace_dir": str(settings.workspace_dir)},
    )
    received = signal.sigwait({signal.SIGTERM, signal.SIGINT})
    logger.info("Worker detenido", extra={"signal": signal.Signals(received).name})
    return 0


if __name__ == "__main__":
    signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGINT})
    raise SystemExit(main())
