"""Panel de uso y coste de IA (WB-8.3, ADR-014): LiteLLM y GitHub Copilot, con caché corta en el proceso.

No es un job (regla 4): son dos lecturas HTTP cortas (``ai_timeout_seconds``, como mucho 10 s aquí) que se guardan
``CACHE_SECONDS`` por fuente. ``refresh`` salta la caché, pero no más de una vez cada ``MIN_REFRESH_SECONDS``. Si cambia
la configuración de una fuente, su entrada deja de valer: la clave de la caché incluye una huella de los valores, que
solo vive en memoria. Una fuente sin configurar o que falla no impide ver la otra.
"""

from __future__ import annotations

import asyncio
import hashlib
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Final

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.domain.ai import settings as ai_settings
from app.domain.ai.errors import AiNotConfiguredError
from app.integrations.doc_organize.ai import (
    AiConnection,
    AiErrorCode,
    AiServiceError,
    FamilyKey,
    UsageReport,
    UsageSourceKey,
    fetch_usage,
)

CACHE_SECONDS: Final = 300
MIN_REFRESH_SECONDS: Final = 30
MAX_TIMEOUT_SECONDS: Final = 10.0
SOURCES: Final[tuple[tuple[UsageSourceKey, FamilyKey], ...]] = (
    ("litellm", "litellm_usage"),
    ("github_copilot", "github_copilot_usage"),
)


@dataclass(frozen=True)
class UsageEntry:
    """Uso de una fuente: el informe, o por qué no lo hay (sin configurar o ``error``)."""

    source: UsageSourceKey
    configured: bool
    fetched_at: datetime | None = None
    report: UsageReport | None = None
    error: AiErrorCode | None = None
    cached: bool = False


@dataclass
class _Slot:
    fingerprint: str
    stored_at: float
    entry: UsageEntry


_cache: dict[UsageSourceKey, _Slot] = {}
_lock = threading.Lock()


def clear_cache() -> None:
    """Vacía la caché (tests y cambios de configuración)."""
    with _lock:
        _cache.clear()


def _fingerprint(connection: AiConnection) -> str:
    material = "\x00".join(f"{k}={v}" for k, v in sorted(connection.values.items()))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


async def _fetch(source: UsageSourceKey, connection: AiConnection) -> UsageEntry:
    now = datetime.now(UTC)
    try:
        report = await fetch_usage(source, connection)
    except AiServiceError as exc:
        return UsageEntry(source=source, configured=True, fetched_at=now, error=exc.code)
    return UsageEntry(source=source, configured=True, fetched_at=now, report=report)


async def _gather(pending: list[tuple[UsageSourceKey, AiConnection]]) -> list[UsageEntry]:
    return list(await asyncio.gather(*(_fetch(source, connection) for source, connection in pending)))


def usage(
    db: Session, settings: Settings, *, refresh: bool = False, clock: Callable[[], float] = time.monotonic
) -> list[UsageEntry]:
    """Uso de las dos fuentes, de la caché si es reciente y no cambió su configuración."""
    now = clock()
    entries: dict[UsageSourceKey, UsageEntry] = {}
    pending: list[tuple[UsageSourceKey, AiConnection]] = []
    fingerprints: dict[UsageSourceKey, str] = {}
    for source, family in SOURCES:
        try:
            connection = ai_settings.connection(db, settings, family)
        except AiNotConfiguredError:
            entries[source] = UsageEntry(source=source, configured=False)
            continue
        connection = replace(connection, timeout_s=min(connection.timeout_s, MAX_TIMEOUT_SECONDS))
        fingerprint = _fingerprint(connection)
        fingerprints[source] = fingerprint
        with _lock:
            slot = _cache.get(source)
        if slot is not None and slot.fingerprint == fingerprint:
            age = now - slot.stored_at
            if age < CACHE_SECONDS and (not refresh or age < MIN_REFRESH_SECONDS):
                entries[source] = replace(slot.entry, cached=True)
                continue
        pending.append((source, connection))
    if pending:
        for entry in asyncio.run(_gather(pending)):
            entries[entry.source] = entry
            with _lock:
                _cache[entry.source] = _Slot(fingerprints[entry.source], now, entry)
    return [entries[source] for source, _ in SOURCES]
