"""Lectura paginada de la caché de doc_organize para la API (WB-5.1).

Es lo único de doc_organize que carga el proceso de la API, y solo al listar documentos: ``doc_organize.cache`` no
importa Docling ni torch (G15; decisión del mantenedor en la Fase 5). Firmas verificadas en el tag ``v0.11.0``::

    async with CacheManager(db_path) as cache:
        await cache.count_entries(search: str | None = None) -> int
        await cache.load_cache_page(limit: int, offset: int, search: str | None = None) -> list[CacheEntry]

``CacheManager`` no tiene modo de solo lectura: al abrir pone WAL y crea la tabla si falta (G21). Por eso aquí solo se
abren cachés que ya existen (las crea el worker al escanear); ``aiosqlite`` espera 5 s si el worker la tiene bloqueada.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path


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


def count_documents(cache_db: Path, search: str | None = None) -> int:
    """Entradas de ``cache_db`` (0 si la caché aún no existe), filtradas por ``search`` en la ruta."""
    if not cache_db.is_file():
        return 0
    from doc_organize.cache import CacheManager

    async def _count() -> int:
        async with CacheManager(cache_db) as cache:
            return int(await cache.count_entries(search or None))

    return asyncio.run(_count())


def documents_page(cache_db: Path, *, limit: int, offset: int, search: str | None = None) -> list[CachedDocument]:
    """Página de ``cache_db`` ordenada por ruta (vacía si la caché aún no existe)."""
    if not cache_db.is_file() or limit <= 0:
        return []
    from doc_organize.cache import CacheManager

    async def _page() -> list[CachedDocument]:
        async with CacheManager(cache_db) as cache:
            entries = await cache.load_cache_page(limit, offset, search or None)
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

    return asyncio.run(_page())
