"""Piezas comunes de las operaciones de proyecto."""

from __future__ import annotations

from typing import Final

from app.db.models import Project
from app.domain.identity.audit import RequestContext
from app.jobs.context import JobFailed

#: Origen de la auditoría que escribe el worker (el actor es quien lanzó el run).
WORKER_CONTEXT: Final = RequestContext(ip=None, user_agent="worker")


def require_project(project: Project | None) -> Project:
    """El proyecto del run, que debe existir y estar activo.

    Raises:
        JobFailed: El run no tiene proyecto o el proyecto se borró mientras esperaba en la cola.
    """
    if project is None or project.status != "active":
        raise JobFailed("project_missing", "El proyecto ya no existe.")
    return project
