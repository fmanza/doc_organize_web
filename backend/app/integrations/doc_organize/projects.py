"""Operaciones de proyecto de doc_organize 0.10.0 (L-4, L-5): vaciar el histórico con el estado separado.

Solo se llama desde el subproceso de un job: importa doc_organize **dentro** de la función, de modo que importar este
módulo (o el paquete) no carga la librería en la API ni en el proceso padre del worker (G15).
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path


class DocOrganizeOperationError(Exception):
    """doc_organize no pudo completar la operación. El mensaje es genérico: el de la librería puede llevar rutas."""


def clear_project_history(output_root: Path, state_root: Path, *, name: str, created_at: datetime) -> None:
    """Vacía las salidas (``output_root``) y el estado (``state_root``) y regenera ``project.json`` en las salidas.

    Usa ``ProjectHistoryCleaner.clear(project, *, state_root=)`` (firma verificada en el tag ``v0.10.0``). ``Project``
    se construye sin ``tenant_id`` (obsoleto desde 0.10.0, L-6c).

    Raises:
        DocOrganizeOperationError: La carpeta de salidas no existe o algún elemento no se pudo borrar.
    """
    from doc_organize import DocOrganizeError, Project, ProjectHistoryCleaner

    project = Project(name=name, root_path=str(output_root), created_at=created_at.isoformat())
    try:
        asyncio.run(ProjectHistoryCleaner().clear(project, state_root=state_root))
    except DocOrganizeError as exc:
        raise DocOrganizeOperationError("doc_organize no pudo vaciar el histórico del proyecto.") from exc
