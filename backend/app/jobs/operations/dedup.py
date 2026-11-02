"""``dedup_preview`` y ``dedup_apply``: duplicados en dos pasos (WB-6.1, L-6; decisiones del mantenedor, Fase 6).

- **Vista previa**: documentos de las cachés de todas las carpetas de origen (hash del último escaneo) más un ``stat``
  de cada uno en el origen (tamaño y fecha, G25); ``find_duplicates``; los grupos se guardan en ``duplicate_groups``
  con rutas relativas y, como mejora opcional, en un Excel. No toca ningún fichero. El modo «nombre parecido» compara
  n×n: solo si quedan como mucho ``MAX_FUZZY_DOCUMENTS`` documentos sin agrupar.
- **Aplicar**: solo los grupos confirmados de una vista previa vigente, con el documento elegido para conservar. Antes
  de mover nada se recalcula el hash de sus miembros: un grupo cuyo contenido cambió desde el escaneo se salta. Cada
  grupo pasa por ``move_group`` (``move``/``copy``/``report_only``), la cancelación se atiende entre grupos y cada
  fichero movido o copiado queda auditado. El informe (``DEDUP_REPORT.json`` y ``DEDUP_HISTORY.jsonl``) va al estado
  del proyecto (L-5). Con ``dry_run`` solo cuenta lo que haría.
"""

from __future__ import annotations

import hashlib
import os
import re
import stat as stat_mode
from pathlib import Path, PurePosixPath
from typing import Any, Final

from sqlalchemy import delete, select

from app.db.models import DuplicateGroupRow, Project, Run
from app.domain.documents.paths import DocumentNamer
from app.domain.duplicates.service import member_key
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction
from app.domain.runs.operations import DedupApplyParams, DedupPreviewParams
from app.domain.scan.state import folder_cache
from app.integrations import doc_organize as library
from app.integrations.doc_organize.dedup import DedupDocument, DedupGroup
from app.jobs.context import JobCancelled, JobContext, JobFailed
from app.jobs.operations._files import project_paths, require_rw, resolve_in
from app.jobs.operations.common import WORKER_CONTEXT, require_project

#: Documentos sin agrupar como máximo para el modo «nombre parecido» (matriz n×n en memoria; decisión C4).
MAX_FUZZY_DOCUMENTS: Final = 5_000
REASON_ORDER: Final = {"exact_duplicate": 0, "version_conflict": 1, "fuzzy_name_match": 2}
#: Rutas fallidas que se guardan en el resultado del run (el total va en ``failed``).
MAX_FAILED_SHOWN: Final = 100
EXPORT_DIR: Final = "export"
_FORMULA: Final = re.compile(r"^[=+\-@\t\r]")


def _folders(ctx: JobContext, project: Project) -> list[tuple[str, Path]]:
    """``(subpath, ruta resuelta)`` de las carpetas de origen que existen; las demás se avisan y se saltan."""
    found: list[tuple[str, Path]] = []
    for subpath in sorted(project.source_subpaths, key=str.casefold):
        try:
            resolved = resolve_in(project.source_location, subpath, ctx)
        except JobFailed as exc:
            if exc.code != "folder_missing":
                raise
            ctx.log(exc.message, level="warning")
            continue
        # Una carpeta sustituida por un enlace a otra de la ubicación no es la carpeta del proyecto: se salta.
        if resolved.relative != subpath:
            ctx.log(f"La carpeta «{subpath}» ya no es la registrada; se salta.", level="warning")
            continue
        found.append((subpath, resolved.absolute))
    return found


# --- vista previa ----------------------------------------------------------------------------------------------------


def _documents(ctx: JobContext, project: Project, state: Path) -> tuple[list[DedupDocument], DocumentNamer, int]:
    """Documentos de las cachés que siguen en el origen, el traductor de rutas y cuántos de la caché ya no están."""
    folders = _folders(ctx, project)
    namer = DocumentNamer([(subpath, [root]) for subpath, root in folders], project.source_location.name)
    cached = library.dedup.cache_documents(folder_cache(state, subpath) for subpath, _ in folders)
    docs: list[DedupDocument] = []
    stale = 0
    for index, (path, sha256) in enumerate(cached, start=1):
        if index % 500 == 0:
            ctx.check_cancelled()
            ctx.progress("dedup_scan", index, len(cached))
        if namer.split(path) is None:
            continue
        try:
            info = os.lstat(path)
        except OSError:
            stale += 1
            continue
        if not stat_mode.S_ISREG(info.st_mode):
            stale += 1
            continue
        docs.append(DedupDocument(path=path, size_bytes=info.st_size, modified_time=info.st_mtime, sha256=sha256))
    ctx.progress("dedup_scan", len(cached), len(cached))
    return docs, namer, stale


def _member(namer: DocumentNamer, doc: DedupDocument, canonical: str) -> dict[str, Any]:
    folder, relative = namer.split(doc.path) or ("", PurePosixPath(doc.path).name)
    return {
        "folder": folder,
        "path": relative,
        "size_bytes": doc.size_bytes,
        "modified_time": doc.modified_time,
        "sha256": doc.sha256,
        "canonical": doc.path == canonical,
    }


def _cell(value: object) -> object:
    """Valor de celda sin fórmulas (un nombre de fichero puede empezar por ``=``)."""
    return f"'{value}" if isinstance(value, str) and _FORMULA.match(value) else value


def _write_excel(ctx: JobContext, project: Project, rows: list[DuplicateGroupRow]) -> None:
    """Mejora opcional: los grupos en ``duplicados.xlsx`` (artefacto del run), sin rutas del servidor."""
    from datetime import UTC, datetime

    from openpyxl import Workbook

    name = re.sub(r"[^\w.-]+", "_", project.name).strip("._")[:80] or "proyecto"
    target = ctx.workdir / EXPORT_DIR / f"{name}-duplicados.xlsx"
    target.parent.mkdir(parents=True, exist_ok=True)
    book = Workbook(write_only=True)
    sheet = book.create_sheet("Duplicados")
    sheet.append(["Grupo", "Motivo", "Se conserva", "Carpeta", "Ruta", "Tamaño (bytes)", "Modificado (UTC)", "SHA-256"])
    for number, row in enumerate(rows, start=1):
        for member in row.members:
            modified = datetime.fromtimestamp(float(member["modified_time"]), UTC).strftime("%Y-%m-%d %H:%M:%S")
            sheet.append(
                [
                    number,
                    row.reason,
                    "sí" if member["canonical"] else "no",
                    _cell(member["folder"]),
                    _cell(member["path"]),
                    member["size_bytes"],
                    modified,
                    member["sha256"],
                ]
            )
    book.save(target)
    ctx.add_artifact(f"{EXPORT_DIR}/{target.name}", name=target.name)


def run_preview(ctx: JobContext, params: DedupPreviewParams, project: Project | None) -> dict[str, Any]:
    """Busca duplicados en las cachés del proyecto y guarda los grupos (no toca ficheros)."""
    project = require_project(project)
    paths = project_paths(project, ctx)
    ctx.progress("dedup_scan", 0, None)
    docs, namer, stale = _documents(ctx, project, paths.state)
    ctx.check_cancelled()
    ctx.progress("dedup_find", 0, None)
    groups = library.dedup.find_groups(docs)
    if params.fuzzy_threshold is not None:
        grouped = {doc.path for group in groups for doc in group.members}
        remaining = len(docs) - len(grouped)
        if remaining > MAX_FUZZY_DOCUMENTS:
            raise JobFailed(
                "fuzzy_too_large",
                f"Hay {remaining} documentos sin agrupar y «nombre parecido» admite como mucho {MAX_FUZZY_DOCUMENTS}: "
                "busca solo duplicados exactos y versiones.",
            )
        groups = library.dedup.find_groups(docs, fuzzy_threshold=params.fuzzy_threshold)
    groups.sort(key=lambda g: (REASON_ORDER.get(g.reason, 9), -max(m.size_bytes for m in g.members)))
    rows = [
        DuplicateGroupRow(
            run_id=ctx.run_id,
            group_id=group.group_id,
            reason=group.reason,
            position=position,
            member_count=len(group.members),
            members=[_member(namer, doc, group.canonical) for doc in group.members],
        )
        for position, group in enumerate(groups)
    ]
    with ctx.session_factory() as db:
        # Solo la última búsqueda del proyecto conserva sus grupos: una nueva sustituye a las anteriores.
        older = select(Run.id).where(
            Run.project_id == project.id, Run.operation == "dedup_preview", Run.id != ctx.run_id
        )
        db.execute(delete(DuplicateGroupRow).where(DuplicateGroupRow.run_id.in_(older)))
        db.add_all(rows)
        db.commit()
    if rows:
        _write_excel(ctx, project, rows)
    ctx.progress("done", 1, 1)
    by_reason = {reason: sum(1 for g in groups if g.reason == reason) for reason in REASON_ORDER}
    return {
        "documents": len(docs),
        "groups": len(groups),
        "exact_groups": by_reason["exact_duplicate"],
        "version_groups": by_reason["version_conflict"],
        "fuzzy_groups": by_reason["fuzzy_name_match"],
        "duplicate_files": sum(len(g.members) - 1 for g in groups),
        "reclaimable_bytes": sum(
            g.members[0].size_bytes * (len(g.members) - 1) for g in groups if g.reason == "exact_duplicate"
        ),
        "stale_cache": stale,
        "fuzzy_threshold": params.fuzzy_threshold,
    }


# --- aplicar ---------------------------------------------------------------------------------------------------------


def _sha256(path: Path) -> str | None:
    """Hash actual del fichero, o ``None`` si ya no es un fichero normal legible."""
    try:
        if not stat_mode.S_ISREG(os.lstat(path).st_mode):
            return None
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def _no_links(root: Path, relative: str) -> Path | None:
    """``root/relative`` si ningún tramo por debajo de ``root`` es un enlace simbólico y el último es un fichero normal.

    No se resuelve la ruta: un enlace (al fichero o a una carpeta intermedia) haría que doc_organize moviera o copiara
    lo que hay al otro lado, fuera del origen.
    """
    current = root
    parts = PurePosixPath(relative).parts
    if not parts or ".." in parts:
        return None
    try:
        for part in parts:
            current = current / part
            if stat_mode.S_ISLNK(os.lstat(current).st_mode):
                return None
        return current if stat_mode.S_ISREG(os.lstat(current).st_mode) else None
    except OSError:
        return None


def _current_group(row: DuplicateGroupRow, roots: dict[str, Path]) -> tuple[DedupGroup, dict[str, str]] | None:
    """El grupo de la vista previa con rutas actuales, o ``None`` si algún miembro cambió, ya no está o es un enlace.

    Devuelve también la traducción ``<carpeta>/<ruta>`` → ruta absoluta para elegir el que se conserva.
    """
    members: list[DedupDocument] = []
    keys: dict[str, str] = {}
    canonical = ""
    for member in row.members:
        root = roots.get(str(member["folder"]))
        absolute = _no_links(root, str(member["path"])) if root is not None else None
        if absolute is None or _sha256(absolute) != member["sha256"]:
            return None
        try:
            info = os.lstat(absolute)
        except OSError:
            return None
        doc = DedupDocument(str(absolute), info.st_size, info.st_mtime, str(member["sha256"]))
        members.append(doc)
        keys[member_key(member)] = doc.path
        if member["canonical"]:
            canonical = doc.path
    return DedupGroup(row.group_id, row.reason, canonical or members[0].path, members), keys


def _prepared(row: DuplicateGroupRow, roots: dict[str, Path], keep: str) -> tuple[DedupGroup, str] | None:
    current = _current_group(row, roots)
    absolute = current[1].get(keep) if current else None
    return (current[0], absolute) if current and absolute else None


def _duplicates_dir(output: Path, duplicates_dir: Path) -> None:
    """``duplicados/`` es una carpeta real dentro de las salidas (no un enlace que lleve las copias a otro sitio).

    Raises:
        JobFailed: ``folder_replaced``.
    """
    duplicates_dir.mkdir(exist_ok=True)
    if duplicates_dir.is_symlink() or duplicates_dir.resolve() != output.resolve() / duplicates_dir.name:
        raise JobFailed(
            "folder_replaced", "La carpeta «duplicados» de las salidas no es una carpeta normal; no se toca."
        )


def run_apply(ctx: JobContext, params: DedupApplyParams, project: Project | None) -> dict[str, Any]:
    """Aplica (o, con ``dry_run``, cuenta) los grupos confirmados de la vista previa ``groups_run_id``."""
    project = require_project(project)
    paths = project_paths(project, ctx)
    if params.mode == "move":
        require_rw(project.source_location)
    if params.mode != "report_only":
        require_rw(project.destination_location)
    # Rutas reales (resueltas una vez por el resolvedor): doc_organize 0.12.1 no sigue enlaces (G26).
    source_root = resolve_in(project.source_location, "", ctx).root
    roots = dict(_folders(ctx, project))
    namer = DocumentNamer([(subpath, [root]) for subpath, root in roots.items()], project.source_location.name)
    keep_of = {choice.group_id: choice.keep for choice in params.groups}
    with ctx.session_factory() as db:
        rows = list(
            db.scalars(
                select(DuplicateGroupRow)
                .where(DuplicateGroupRow.run_id == params.groups_run_id, DuplicateGroupRow.group_id.in_(list(keep_of)))
                .order_by(DuplicateGroupRow.position)
            )
        )
        for row in rows:
            db.expunge(row)

    if params.dry_run:
        ready: list[tuple[DedupGroup, str]] = []
        changed = 0
        for index, row in enumerate(rows, start=1):
            ctx.check_cancelled()
            ctx.progress("dedup_verify", index, len(rows))
            prepared = _prepared(row, roots, keep_of[row.group_id])
            if prepared is None:
                changed += 1
            else:
                ready.append(prepared)
        return {
            "mode": params.mode,
            "groups": len(ready),
            "files": sum(len(group.members) - 1 for group, _ in ready),
            "bytes": sum(m.size_bytes for group, keep in ready for m in group.members if m.path != keep),
            "skipped_changed": changed,
        }

    duplicates_dir, report_dir = library.dedup.dedup_dirs(paths.output.absolute, paths.state)
    if params.mode != "report_only":
        _duplicates_dir(paths.output.absolute, duplicates_dir)
    action = AuditAction.DUPLICATE_MOVE if params.mode == "move" else AuditAction.DUPLICATE_COPY

    def on_group(index: int, total: int, group: DedupGroup | None, keep: str, failed: list[str]) -> None:
        ctx.progress("dedup_apply", index, total, namer.display(group.members[0].path) if group else None)
        if group is None or params.mode == "report_only":
            return
        done = [m.path for m in group.members if m.path != keep and m.path not in failed]
        with ctx.session_factory() as db:
            for path in done:
                audit.record(
                    db,
                    action=action,
                    ctx=WORKER_CONTEXT,
                    actor_id=ctx.created_by,
                    target_type="project",
                    target_id=project.id,
                    details={"run_id": ctx.run_id, "group_id": group.group_id, "path": namer.display(path)},
                )
            db.commit()

    outcome = library.dedup.ApplyOutcome()
    result: dict[str, Any] = {"mode": params.mode, "groups": len(rows)}
    try:
        # Cada grupo se comprueba (hash, sin enlaces) justo antes de aplicarlo y se aplica entero: la cancelación se
        # atiende entre grupos, nunca a mitad de un fichero.
        with ctx.uninterruptible():
            outcome = library.dedup.apply_groups(
                rows,
                prepare=lambda row: _prepared(row, roots, keep_of[row.group_id]),
                duplicates_dir=duplicates_dir,
                report_dir=report_dir,
                relative_to=source_root,  # duplicados/<carpeta>/<ruta> (G24)
                mode=params.mode,
                on_group=on_group,
                is_cancelled=lambda: ctx.cancelled,
            )
    except library.DocOrganizeOperationError:
        raise JobFailed(
            "dedup_report_failed", "Se aplicaron los grupos, pero no se pudo escribir el informe."
        ) from None
    finally:
        result.update(
            processed=outcome.processed,
            failed=len(outcome.failed),
            failed_paths=[namer.display(p) for p in outcome.failed[:MAX_FAILED_SHOWN]],
            groups_done=outcome.groups_done,
            skipped_changed=outcome.skipped,
        )
        # El resumen se audita también si algo falla a mitad: lo ya movido no puede quedar sin rastro.
        with ctx.session_factory() as db:
            audit.record(
                db,
                action=AuditAction.DUPLICATE_APPLY,
                ctx=WORKER_CONTEXT,
                actor_id=ctx.created_by,
                target_type="project",
                target_id=project.id,
                details={k: v for k, v in result.items() if k != "failed_paths"} | {"run_id": ctx.run_id},
            )
            db.commit()
    if outcome.cancelled:
        raise JobCancelled(result)
    ctx.progress("done", 1, 1)
    return result
