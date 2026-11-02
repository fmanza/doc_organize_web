"""Duplicados de un proyecto (Fase 6): grupos de una vista previa, validación de lo que se aplica y última aplicación.

Dos pasos (ADR-009 propuesto): ``dedup_preview`` guarda los grupos en ``duplicate_groups`` sin tocar ficheros; el
usuario confirma grupos y elige qué conservar, y ``dedup_apply`` aplica **solo** esos grupos, con su propia vista previa
(``dry_run``) y el nombre del proyecto. Las rutas son siempre relativas a la ubicación de origen (``<carpeta>/<ruta>``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Final

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import ACTIVE_RUN_STATUSES, DuplicateGroupRow, Project, Run, utcnow
from app.domain.duplicates.errors import DuplicatePreviewRequiredError, GroupNotInPreviewError, SourceReadOnlyError
from app.domain.runs.operations import DedupApplyParams

#: Vigencia de una vista previa de duplicados para aplicarla (después, otra escritura pudo cambiar el origen).
PREVIEW_TTL: Final = timedelta(minutes=60)
REASONS: Final = ("exact_duplicate", "version_conflict", "fuzzy_name_match")


def member_key(member: dict[str, Any]) -> str:
    """Identificador de un miembro de un grupo: ``<carpeta>/<ruta>`` (solo ``<ruta>`` en la raíz de la ubicación).

    Las carpetas de origen no se anidan y la raíz, si es carpeta, es la única: la clave no es ambigua.
    """
    folder, path = str(member["folder"]), str(member["path"])
    return f"{folder}/{path}" if folder else path


@dataclass(frozen=True)
class LastRuns:
    """Última vista previa de duplicados y última aplicación real del proyecto (terminadas con éxito)."""

    preview: Run | None
    apply: Run | None


def preview_run(db: Session, project: Project, run_id: str) -> Run:
    """La vista previa ``run_id`` del proyecto, vigente para aplicarla.

    Raises:
        DuplicatePreviewRequiredError: No existe, es de otro proyecto u operación, no terminó bien, caducó o hubo otra
            escritura en el proyecto después (pudo cambiar el origen).
    """
    run = db.get(Run, run_id)
    if run is None or run.project_id != project.id or run.operation != "dedup_preview" or run.status != "succeeded":
        raise DuplicatePreviewRequiredError("Lanza primero la búsqueda de duplicados.")
    if run.finished_at is None or utcnow() - run.finished_at > PREVIEW_TTL:
        raise DuplicatePreviewRequiredError("La búsqueda de duplicados ha caducado: vuelve a lanzarla.")
    since = run.started_at or run.created_at
    newer = select(Run.id).where(
        Run.project_id == project.id,
        Run.is_write.is_(True),
        Run.status.in_(ACTIVE_RUN_STATUSES) | (Run.created_at > run.created_at) | (Run.finished_at >= since),
    )
    if db.scalar(newer.limit(1)) is not None or project.updated_at > run.created_at:
        raise DuplicatePreviewRequiredError(
            "El proyecto ha cambiado desde la búsqueda de duplicados: vuelve a lanzarla."
        )
    return run


def validate_apply(db: Session, project: Project, params: DedupApplyParams) -> DedupApplyParams:
    """Comprueba la vista previa, los grupos (sin repetir), lo que se conserva y la ubicación.

    Raises:
        DuplicatePreviewRequiredError: Vista previa no válida.
        GroupNotInPreviewError: Un grupo no es de la vista previa o ``keep`` no es de su grupo.
        SourceReadOnlyError: ``move`` con la ubicación de origen de solo lectura.
    """
    run = preview_run(db, project, params.groups_run_id)
    if params.mode == "move" and project.source_location.access != "rw":
        raise SourceReadOnlyError("Elige «Copiar» o «Solo informe»: el origen es de solo lectura.")
    wanted = {choice.group_id: choice.keep for choice in params.groups}
    if len(wanted) != len(params.groups):
        raise GroupNotInPreviewError("Un grupo aparece más de una vez.")
    rows = {
        row.group_id: row
        for row in db.scalars(
            select(DuplicateGroupRow).where(
                DuplicateGroupRow.run_id == run.id, DuplicateGroupRow.group_id.in_(list(wanted))
            )
        )
    }
    for group_id, keep in wanted.items():
        row = rows.get(group_id)
        if row is None:
            raise GroupNotInPreviewError(f"El grupo {group_id} no está en la búsqueda de duplicados.")
        if keep not in {member_key(m) for m in row.members}:
            raise GroupNotInPreviewError(f"«{keep}» no es de su grupo de duplicados.")
    return params


def list_groups(
    db: Session, run_id: str, *, reason: str | None, limit: int, offset: int
) -> tuple[list[DuplicateGroupRow], int]:
    """Grupos de una vista previa en su orden (exactos, versiones, parecidos), paginados."""
    query = select(DuplicateGroupRow).where(DuplicateGroupRow.run_id == run_id)
    if reason:
        query = query.where(DuplicateGroupRow.reason == reason)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(DuplicateGroupRow.position).limit(limit).offset(offset)).all()
    return list(rows), int(total)


def last_runs(db: Session, project_id: int) -> LastRuns:
    """Última vista previa y última aplicación real (no ``dry_run``) terminadas con éxito."""

    def _last(operation: str, *, real: bool = False) -> Run | None:
        query = select(Run).where(Run.project_id == project_id, Run.operation == operation, Run.status == "succeeded")
        if real:
            query = query.where(Run.is_write.is_(True))
        return db.scalars(query.order_by(Run.finished_at.desc()).limit(1)).first()

    return LastRuns(preview=_last("dedup_preview"), apply=_last("dedup_apply", real=True))
