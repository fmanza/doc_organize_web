"""Implementaciones de las operaciones, una por módulo (``jobs.instructions.md``).

Cada una recibe el contexto del job, sus parámetros ya validados y el proyecto (desvinculado de la sesión, con sus
ubicaciones cargadas) y devuelve el ``result`` del run (solo recuentos y rutas relativas: nunca rutas del contenedor).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Final

from app.db.models import Project
from app.jobs.context import JobContext
from app.jobs.operations import history_clear, noop, project_delete, project_move, scan

Operation = Callable[[JobContext, Any, Project | None], dict[str, Any]]

REGISTRY: Final[dict[str, Operation]] = {
    "noop": noop.run,
    "history_clear": history_clear.run,
    "project_move": project_move.run,
    "project_delete": project_delete.run,
    "scan": scan.run,
}
