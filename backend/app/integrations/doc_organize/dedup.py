"""Duplicados con ``DeduplicationManager`` de doc_organize 0.12.1 (WB-6.1, L-6, L-11a).

Solo se llama desde el subproceso de un job (importa doc_organize **dentro** de las funciones). Firmas verificadas en el
tag ``v0.12.1``::

    DeduplicationManager().find_duplicates(docs: list[DocumentMetadata], fuzzy_threshold: int | None = None)
        -> list[DuplicateGroup]
    await move_group(group, duplicates_dir, *, mode: DedupMode = "move", relative_to: Path | None = None)
        -> tuple[int, int, list[str]]
    await finalize_report(groups, duplicates_dir, exact_moved, version_resolved, started_at=None,
                          failed_paths=None, report_dir=None, mode="move") -> DeduplicationReport
    DocumentMetadata(full_path, display_name, extension, size_bytes, modified_time, sha256_hash)
    DuplicateGroup(group_id, canonical_doc, duplicates, reason, user_choice)

No se usa ``ScanCommand.deduplicate_streaming``: rehashea todo el origen y mueve todos los grupos sin revisión. La web
compone la detección y el movimiento por grupo, con cancelación entre grupos. Rutas absolutas del contenedor dentro de
esta capa; el job las convierte en relativas.

Desde la 0.12.1 doc_organize no mueve ni copia nada que pase por un enlace simbólico (G26): las rutas de origen, de
``duplicados/`` y ``relative_to`` deben ser **reales** (las del resolvedor de ubicaciones, resueltas una vez).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.integrations.doc_organize.projects import DocOrganizeOperationError


@dataclass(frozen=True)
class DedupDocument:
    """Documento candidato: ruta absoluta del contenedor, tamaño, fecha de modificación y hash SHA-256."""

    path: str
    size_bytes: int
    modified_time: float
    sha256: str


@dataclass(frozen=True)
class DedupGroup:
    """Grupo de duplicados: ``reason`` es ``exact_duplicate``, ``version_conflict`` o ``fuzzy_name_match``;
    ``canonical`` es la ruta que doc_organize conserva por defecto (la más antigua)."""

    group_id: str
    reason: str
    canonical: str
    members: list[DedupDocument]


@dataclass
class ApplyOutcome:
    """Resultado de aplicar grupos.

    Attributes:
        processed: Ficheros movidos, copiados o (``report_only``) señalados.
        failed: Rutas absolutas que no se pudieron mover o copiar.
        groups_done: Grupos aplicados antes de terminar o de cancelar.
        skipped: Grupos que cambiaron desde la vista previa (``prepare`` devolvió ``None``).
        cancelled: Paró entre dos grupos por cancelación.
    """

    processed: int = 0
    skipped: int = 0
    failed: list[str] = field(default_factory=list)
    groups_done: int = 0
    cancelled: bool = False


def cache_documents(cache_dbs: Iterable[Path]) -> list[tuple[str, str]]:
    """``(ruta absoluta, sha256)`` de todas las entradas de las cachés (``load_cache_entries``, sin crearlas)."""
    from doc_organize.export import load_cache_entries

    entries = asyncio.run(load_cache_entries(list(cache_dbs)))
    return [(entry.file_path, entry.sha256_hash) for entry in entries]


def _metadata(doc: DedupDocument) -> Any:
    from doc_organize import DocumentMetadata

    path = Path(doc.path)
    return DocumentMetadata(
        full_path=doc.path,
        display_name=path.name,
        extension=path.suffix.lstrip(".").lower(),
        size_bytes=doc.size_bytes,
        modified_time=doc.modified_time,
        sha256_hash=doc.sha256,
    )


def find_groups(docs: list[DedupDocument], fuzzy_threshold: int | None = None) -> list[DedupGroup]:
    """Grupos de duplicados exactos, conflictos de versión y (con ``fuzzy_threshold``) nombres parecidos."""
    from doc_organize import DeduplicationManager

    by_path = {doc.path: doc for doc in docs}
    groups = DeduplicationManager().find_duplicates([_metadata(doc) for doc in docs], fuzzy_threshold=fuzzy_threshold)
    return [
        DedupGroup(
            group_id=group.group_id,
            reason=group.reason.value,
            canonical=group.canonical_doc.full_path,
            members=[by_path[m.full_path] for m in [group.canonical_doc, *group.duplicates]],
        )
        for group in groups
    ]


def apply_groups[T](
    items: list[T],
    *,
    prepare: Callable[[T], tuple[DedupGroup, str] | None],
    duplicates_dir: Path,
    report_dir: Path,
    relative_to: Path,
    mode: str,
    on_group: Callable[[int, int, DedupGroup | None, str, list[str]], None],
    is_cancelled: Callable[[], bool],
) -> ApplyOutcome:
    """Aplica cada elemento con ``move_group`` y escribe **siempre** el informe con ``finalize_report``.

    ``prepare(elemento)`` se llama justo antes de mover su grupo (no en una pasada previa): devuelve el grupo con las
    rutas comprobadas en ese momento y la ruta que se conserva, o ``None`` si el grupo cambió (se salta). Un fallo de
    doc_organize en un grupo cuenta sus ficheros como fallidos y se sigue con los demás. Para entre grupos si se
    cancela. ``on_group(índice, total, grupo o None, conservado, fallidos)`` se llama tras cada elemento. Cada descartado
    va a ``duplicates_dir / <ruta relativa a relative_to>`` (G24); uno que no cuelgue de ``relative_to`` falla.

    Raises:
        DocOrganizeOperationError: doc_organize no pudo escribir el informe (lo aplicado ya está auditado).
    """
    from doc_organize import DeduplicationManager, DocOrganizeError, DuplicateGroup, DuplicateReason

    manager = DeduplicationManager()
    outcome = ApplyOutcome()
    applied: list[Any] = []
    started = datetime.now(UTC)
    counts = {"exact": 0, "versions": 0}

    async def _loop() -> None:
        for index, item in enumerate(items, start=1):
            if is_cancelled():
                outcome.cancelled = True
                return
            prepared = prepare(item)
            if prepared is None:
                outcome.skipped += 1
                on_group(index, len(items), None, "", [])
                continue
            group, keep = prepared
            members = {doc.path: _metadata(doc) for doc in group.members}
            library_group = DuplicateGroup(
                group_id=group.group_id,
                canonical_doc=members[group.canonical],
                duplicates=[m for path, m in members.items() if path != group.canonical],
                reason=DuplicateReason(group.reason),
                user_choice=members[keep],
            )
            try:
                exact, versions, failed = await manager.move_group(
                    library_group, duplicates_dir, mode=mode, relative_to=relative_to
                )
            except DocOrganizeError:  # p. ej. InvalidPathError: el grupo entero falla, los demás siguen
                exact, versions, failed = 0, 0, [path for path in members if path != keep]
            counts["exact"] += exact
            counts["versions"] += versions
            # move_group cuenta los parecidos como versiones: lo hecho es lo que no falló.
            outcome.processed += len(members) - 1 - len(failed)
            outcome.failed.extend(failed)
            outcome.groups_done += 1
            applied.append(library_group)
            on_group(index, len(items), group, keep, failed)

    async def _apply() -> None:
        try:
            await _loop()
        finally:
            await manager.finalize_report(
                applied,
                duplicates_dir,
                counts["exact"],
                counts["versions"],
                started_at=started,
                failed_paths=outcome.failed,
                report_dir=report_dir,
                mode=mode,
            )

    try:
        asyncio.run(_apply())
    except DocOrganizeError as exc:
        raise DocOrganizeOperationError("doc_organize no pudo escribir el informe de duplicados.") from exc
    return outcome


def dedup_dirs(output_root: Path, state_root: Path) -> tuple[Path, Path]:
    """``(duplicados/, carpeta del informe)``: ``ProjectLayout.duplicates_dir`` y ``dedup_report_dir`` (L-5)."""
    from doc_organize import ProjectLayout

    layout = ProjectLayout(output_root, state_root=state_root)
    return Path(layout.duplicates_dir), Path(layout.dedup_report_dir)
