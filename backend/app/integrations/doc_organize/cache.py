"""Lectura paginada de la caché de doc_organize para la API (WB-5.1).

Es lo único de doc_organize que carga el proceso de la API, y solo al listar documentos: ``doc_organize.cache`` no
importa Docling ni torch (G15; decisión del mantenedor en la Fase 5). Firmas verificadas en el tag ``v0.12.0``::

    async with CacheManager(db_path, read_only=True) as cache:
        await cache.count_entries(search=None, *, relative_to=None, conversion_status=None) -> int
        await cache.load_cache_page(limit, offset, search=None, *, relative_to=None, conversion_status=None,
                                    order_by="file_path", descending=False) -> list[CacheEntry]

``order_by`` y ``descending`` llegan con doc_organize 1.2.0 (G40/L-18, verificados en el wheel): empates por
``file_path`` ascendente y los ``NULL`` al final en los dos sentidos. doc_organize 1.6.0 (G43) añade el orden por
``mime_type``, ``created_time`` y ``owner_name`` (este sin distinguir mayúsculas, ``COLLATE NOCASE``), el filtro
``mime_type`` (uno o varios tipos, igualdad exacta) en ``count_entries`` y ``load_cache_page``, y
``list_mime_types(search=None, *, relative_to=None, conversion_status=None) -> list[tuple[str, int]]``.

Con ``read_only=True`` (G21) la API no escribe en la caché (URI ``mode=ro``, sin WAL, ``CREATE`` ni ``ALTER``) y una
caché que aún no existe da ``CacheNotFoundError``. ``relative_to`` (G22) limita a las entradas bajo la carpeta y hace
que ``search`` mire la ruta **relativa** a ella, no la del contenedor.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

#: Columnas por las que ``documents_page`` ordena (``doc_organize.cache.CacheOrderBy``, doc_organize 1.2.0; las tres
#: últimas desde 1.6.0, G43).
CacheOrder = Literal[
    "file_path",
    "timestamp",
    "conversion_status",
    "status",
    "error_retry_count",
    "mime_type",
    "created_time",
    "owner_name",
]
#: Atributo de ``CachedDocument`` con el valor de cada orden, para mezclar páginas de varias cachés igual que la librería.
ORDER_ATTRIBUTE: Final[dict[CacheOrder, str]] = {
    "file_path": "path",
    "timestamp": "updated_at",
    "conversion_status": "conversion_status",
    "status": "status",
    "error_retry_count": "error_retry_count",
    "mime_type": "mime_type",
    "created_time": "created_time",
    "owner_name": "owner_name",
}
#: Órdenes que la librería hace sin distinguir mayúsculas (``COLLATE NOCASE`` de SQLite: solo las letras ASCII).
CASE_INSENSITIVE_ORDERS: Final[frozenset[CacheOrder]] = frozenset({"owner_name"})


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
        mime_type: Tipo MIME según la extensión (doc_organize 1.5.0); ``None`` en entradas anteriores o extensión
            desconocida.
        created_time: Marca Unix de creación del fichero (``st_birthtime``); ``None`` en Linux o en entradas anteriores.
        file_permissions: Permisos POSIX en octal; ``None`` en Windows o en entradas anteriores.
        owner_name: Cuenta propietaria, solo si el proyecto la guarda (``capture_owner``).
    """

    path: str
    status: str
    conversion_status: str | None
    error_message: str | None
    error_retry_count: int
    updated_at: float
    mime_type: str | None = None
    created_time: float | None = None
    file_permissions: str | None = None
    owner_name: str | None = None


def count_documents(
    cache_db: Path,
    search: str | None = None,
    *,
    root: Path,
    conversion_status: str | None = None,
    mime_type: Sequence[str] | None = None,
) -> int:
    """Entradas de ``cache_db`` bajo ``root`` (0 si la caché aún no existe), filtradas por ``search`` en la ruta relativa
    a ``root``, por estado de conversión y por tipo MIME (alguno de ``mime_type``, 1.6.0)."""
    from doc_organize import CacheNotFoundError
    from doc_organize.cache import CacheManager

    async def _count() -> int:
        async with CacheManager(cache_db, read_only=True) as cache:
            return int(
                await cache.count_entries(
                    search or None,
                    relative_to=root,
                    conversion_status=conversion_status,
                    mime_type=list(mime_type) if mime_type else None,
                )
            )

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
    mime_type: Sequence[str] | None = None,
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
                mime_type=list(mime_type) if mime_type else None,
            )
        return [
            CachedDocument(
                path=entry.file_path,
                status=entry.status.value,
                conversion_status=entry.conversion_status.value if entry.conversion_status else None,
                error_message=entry.error_message,
                error_retry_count=entry.error_retry_count,
                updated_at=entry.timestamp,
                mime_type=entry.mime_type,
                created_time=entry.created_time,
                file_permissions=entry.file_permissions,
                owner_name=entry.owner_name,
            )
            for entry in entries
        ]

    try:
        return asyncio.run(_page())
    except CacheNotFoundError:
        return []


def mime_types(
    cache_db: Path, search: str | None = None, *, root: Path, conversion_status: str | None = None
) -> list[tuple[str, int]]:
    """``(tipo MIME, entradas)`` de ``cache_db`` bajo ``root`` con los mismos filtros que ``count_documents`` (salvo el
    tipo), de más a menos entradas; vacía si la caché aún no existe o es anterior a 1.5.0 (doc_organize 1.6.0, G43)."""
    from doc_organize import CacheNotFoundError
    from doc_organize.cache import CacheManager

    async def _types() -> list[tuple[str, int]]:
        async with CacheManager(cache_db, read_only=True) as cache:
            found = await cache.list_mime_types(search or None, relative_to=root, conversion_status=conversion_status)
        return [(str(mime), int(count)) for mime, count in found]

    try:
        return asyncio.run(_types())
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
