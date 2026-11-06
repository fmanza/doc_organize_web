"""Lectura paginada de la caché de doc_organize para la API (WB-5.1).

Es lo único de doc_organize que carga el proceso de la API, y solo al listar documentos: ``doc_organize.cache`` no
importa Docling ni torch (G15; decisión del mantenedor en la Fase 5). Firmas verificadas en el tag ``v0.12.0``::

    async with CacheManager(db_path, read_only=True) as cache:
        await cache.count_entries(search=None, *, relative_to=None, conversion_status=None) -> int
        await cache.load_cache_page(limit, offset, search=None, *, relative_to=None, conversion_status=None,
                                    order_by="file_path", descending=False) -> list[CacheEntry]

``order_by`` y ``descending`` llegan con doc_organize 1.2.0 (G40/L-18, verificados en el wheel): empates por
``file_path`` ascendente y los ``NULL`` al final en los dos sentidos.

Con ``read_only=True`` (G21) la API no escribe en la caché (URI ``mode=ro``, sin WAL, ``CREATE`` ni ``ALTER``) y una
caché que aún no existe da ``CacheNotFoundError``. ``relative_to`` (G22) limita a las entradas bajo la carpeta y hace
que ``search`` mire la ruta **relativa** a ella, no la del contenedor.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

#: Columnas por las que ``documents_page`` ordena (``doc_organize.cache.CacheOrderBy``, doc_organize 1.2.0).
CacheOrder = Literal["file_path", "timestamp", "conversion_status", "status", "error_retry_count"]
#: Atributo de ``CachedDocument`` con el valor de cada orden, para mezclar páginas de varias cachés igual que la librería.
ORDER_ATTRIBUTE: Final[dict[CacheOrder, str]] = {
    "file_path": "path",
    "timestamp": "updated_at",
    "conversion_status": "conversion_status",
    "status": "status",
    "error_retry_count": "error_retry_count",
}


@dataclass(frozen=True)
class CachedDocument:
    """Entrada de caché (``CacheEntry``) con tipos propios; ``path`` es la ruta absoluta del contenedor.

    Attributes:
        path: Ruta absoluta del documento de origen (quien llama la hace relativa antes de mostrarla).
        status: ``new``, ``modified``, ``unchanged`` o ``deleted``.
        conversion_status: ``success``, ``error``, ``pending``… o ``None``.
        error_message: Último error de conversión, sin sanear.
        error_retry_count: Fallos seguidos sin cambios en el fichero.
        updated_at: Marca Unix de la última actualización de la entrada.
    """

    path: str
    status: str
    conversion_status: str | None
    error_message: str | None
    error_retry_count: int
    updated_at: float


def count_documents(
    cache_db: Path, search: str | None = None, *, root: Path, conversion_status: str | None = None
) -> int:
    """Entradas de ``cache_db`` bajo ``root`` (0 si la caché aún no existe), filtradas por ``search`` en la ruta relativa
    a ``root`` y por estado de conversión."""
    from doc_organize import CacheNotFoundError
    from doc_organize.cache import CacheManager

    async def _count() -> int:
        async with CacheManager(cache_db, read_only=True) as cache:
            return int(await cache.count_entries(search or None, relative_to=root, conversion_status=conversion_status))

    try:
        return asyncio.run(_count())
    except CacheNotFoundError:
        return 0


def documents_page(
    cache_db: Path,
    *,
    root: Path,
    limit: int,
    offset: int,
    search: str | None = None,
    conversion_status: str | None = None,
    order_by: CacheOrder = "file_path",
    descending: bool = False,
) -> list[CachedDocument]:
    """Página de ``cache_db`` (vacía si la caché aún no existe), con los mismos filtros, ordenada por ``order_by``
    (por ruta si no se dice otra cosa; empates por ruta y los vacíos al final)."""
    if limit <= 0:
        return []
    from doc_organize import CacheNotFoundError
    from doc_organize.cache import CacheManager

    async def _page() -> list[CachedDocument]:
        async with CacheManager(cache_db, read_only=True) as cache:
            entries = await cache.load_cache_page(
                limit,
                offset,
                search or None,
                relative_to=root,
                conversion_status=conversion_status,
                order_by=order_by,
                descending=descending,
            )
        return [
            CachedDocument(
                path=entry.file_path,
                status=entry.status.value,
                conversion_status=entry.conversion_status.value if entry.conversion_status else None,
                error_message=entry.error_message,
                error_retry_count=entry.error_retry_count,
                updated_at=entry.timestamp,
            )
            for entry in entries
        ]

    try:
        return asyncio.run(_page())
    except CacheNotFoundError:
        return []


def output_paths(folder: str, relative: str) -> tuple[str, str, str]:
    """``(markdown, json, imágenes)`` de un documento, relativos a ``Conversión/`` (G20, resuelto en 0.12.0).

    Usa ``resolve_output_paths``/``resolve_images_dir`` de ``doc_organize.projects.layout`` (sin Docling) sobre una raíz
    ficticia: solo importa la ruta relativa del documento dentro de su carpeta de origen.
    """
    from doc_organize import resolve_images_dir, resolve_output_paths

    root = Path("/dow-source")
    output = Path("/dow-output")
    target = output / folder if folder else output
    markdown, json_path = resolve_output_paths(str(root / relative), target, [str(root)])
    images = resolve_images_dir(markdown)
    markdown_rel, json_rel, images_rel = (p.relative_to(output).as_posix() for p in (markdown, json_path, images))
    return markdown_rel, json_rel, images_rel
