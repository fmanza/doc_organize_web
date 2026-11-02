"""``search_index``: pone al día el índice de búsqueda de texto completo del proyecto (mejora opcional, Fase 5).

El escaneo lo hace también al terminar (``reindex_project``), así que este run solo hace falta para un proyecto
escaneado antes de la 0.6.0 o si el índice se ha perdido.
"""

from __future__ import annotations

from typing import Any

from app.db.models import Project
from app.domain.runs.operations import SearchIndexParams
from app.domain.scan.state import CONVERSION_DIR
from app.domain.search.index import IndexStats, reindex, search_db
from app.jobs.context import JobContext
from app.jobs.operations._files import ProjectPaths, project_paths
from app.jobs.operations.common import require_project


def reindex_project(ctx: JobContext, paths: ProjectPaths, *, cancellable: bool = True) -> IndexStats:
    """Reindexa el Markdown de ``Conversión/`` del proyecto con progreso y, si ``cancellable``, cancelación.

    Al final de un escaneo no se cancela: lo convertido ya está hecho y una cancelación tardía perdería sus recuentos.
    """
    return reindex(
        search_db(paths.state),
        paths.output.absolute / CONVERSION_DIR,
        check_cancelled=ctx.check_cancelled if cancellable else lambda: None,
        on_progress=lambda done, total: ctx.progress("search_index", done, total),
    )


def run(ctx: JobContext, params: SearchIndexParams, project: Project | None) -> dict[str, Any]:
    """Reindexa y devuelve los recuentos."""
    project = require_project(project)
    stats = reindex_project(ctx, project_paths(project, ctx))
    return {"indexed": stats.total, "added": stats.added, "updated": stats.updated, "removed": stats.removed}
