"""Calidad de la clasificación (W5, doc_organize 2.0 G3): la referencia en Excel del proyecto y las comprobaciones al
encolar la evaluación y la clasificación de prueba.

La referencia se guarda en el volumen local de datos (``DOW_DATA_DIR/projects/<id>/quality/gold.xlsx``, con su
configuración en ``gold.json``), no en el destino: es un fichero de trabajo de la app. Subirla o borrarla: propietario
o editor, auditado sin el contenido. Se comprueba al subirla (``load_gold_xlsx``): hoja, columna del documento y
columnas de los ejes.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Project, User
from app.domain.context.errors import GoldInvalidError, GoldNotFoundError
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction, RequestContext
from app.domain.projects.service import state_dir
from app.domain.runs.operations import (
    ContextDryRunParams,
    ContextEvaluateParams,
    TaxonomyAgentParams,
    TaxonomyCheckParams,
)
from app.integrations.doc_organize import evaluation as library

#: Tamaño máximo del Excel de referencia.
MAX_GOLD_BYTES: Final = 5 * 1024 * 1024
#: Un ``.xlsx`` es un ZIP: empieza por ``PK``.
_XLSX_MAGIC: Final = b"PK\x03\x04"
GOLD_FILE: Final = "gold.xlsx"
GOLD_META: Final = "gold.json"


@dataclass(frozen=True)
class Gold:
    """Referencia en Excel del proyecto: configuración y resumen (sin el contenido)."""

    filename: str
    sheet: str
    document_column: str
    columns: dict[str, str]
    labels: int
    axes: list[str]
    uploaded_at: str
    uploaded_by: str | None


def _folder(settings: Settings, project: Project) -> Path:
    return state_dir(settings, project.id) / "quality"


def gold_spec(settings: Settings, project: Project, source: library.GoldSource) -> library.GoldSpec:
    """Lo que necesita el job para cargar la referencia (``source``: el Excel subido o las decisiones).

    Raises:
        GoldNotFoundError: Se pide el Excel y no hay ninguno subido.
    """
    if source == "decisions":
        return library.GoldSpec(source="decisions")
    found = read_gold(settings, project)
    if found is None:
        raise GoldNotFoundError("Sube antes una referencia en Excel o usa las decisiones del proyecto.")
    return library.GoldSpec(
        source="xlsx",
        path=_folder(settings, project) / GOLD_FILE,
        sheet=found.sheet,
        document_column=found.document_column,
        columns=found.columns or None,
    )


def read_gold(settings: Settings, project: Project) -> Gold | None:
    """La referencia subida, o ``None``."""
    meta = _folder(settings, project) / GOLD_META
    if not meta.is_file() or not (_folder(settings, project) / GOLD_FILE).is_file():
        return None
    data: dict[str, Any] = json.loads(meta.read_text(encoding="utf-8"))
    return Gold(**data)


def upload_gold(
    db: Session,
    settings: Settings,
    project: Project,
    content: bytes,
    *,
    filename: str,
    sheet: str,
    document_column: str,
    columns: dict[str, str],
    actor: User,
    ctx: RequestContext,
) -> Gold:
    """Comprueba y guarda la referencia (sustituye a la anterior).

    Raises:
        GoldInvalidError: Demasiado grande, no es un Excel, falta la hoja o la columna, o no tiene etiquetas.
    """
    if len(content) > MAX_GOLD_BYTES:
        raise GoldInvalidError(f"La referencia pasa de {MAX_GOLD_BYTES // (1024 * 1024)} MB.")
    if not content.startswith(_XLSX_MAGIC):
        raise GoldInvalidError("La referencia tiene que ser un Excel (.xlsx).")
    folder = _folder(settings, project)
    folder.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=folder, prefix=".gold-", suffix=".xlsx")
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
        spec = library.GoldSpec(
            source="xlsx",
            path=Path(temporary),
            sheet=sheet,
            document_column=document_column,
            columns=columns or None,
        )
        try:
            summary = library.read_gold(spec)
        except library.GoldInvalidError as exc:
            raise GoldInvalidError(str(exc)) from None
        if summary.labels == 0:
            raise GoldInvalidError("La referencia no tiene ningún documento etiquetado en esas columnas.")
        os.replace(temporary, folder / GOLD_FILE)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(temporary)
    gold = Gold(
        filename=Path(filename).name[:255] or GOLD_FILE,
        sheet=sheet,
        document_column=document_column,
        columns=columns,
        labels=summary.labels,
        axes=summary.axes,
        uploaded_at=datetime.now(UTC).isoformat(timespec="seconds"),
        uploaded_by=actor.username,
    )
    (folder / GOLD_META).write_text(json.dumps(gold.__dict__, ensure_ascii=False), encoding="utf-8")
    audit.record(
        db,
        action=AuditAction.PROJECT_GOLD_UPLOAD,
        ctx=ctx,
        actor_id=actor.id,
        target_type="project",
        target_id=project.id,
        details={"labels": summary.labels, "axes": summary.axes},
    )
    db.commit()
    return gold


def delete_gold(db: Session, settings: Settings, project: Project, *, actor: User, ctx: RequestContext) -> None:
    """Borra la referencia subida (sin ella, nada que hacer)."""
    folder = _folder(settings, project)
    existed = False
    for name in (GOLD_FILE, GOLD_META):
        with contextlib.suppress(FileNotFoundError):
            (folder / name).unlink()
            existed = True
    if existed:
        audit.record(
            db,
            action=AuditAction.PROJECT_GOLD_DELETE,
            ctx=ctx,
            actor_id=actor.id,
            target_type="project",
            target_id=project.id,
        )
        db.commit()


def validate_evaluate(db: Session, settings: Settings, project: Project, params: ContextEvaluateParams) -> None:
    """Al encolar la evaluación: hay contexto y referencia.

    Raises:
        ContextNotFoundError, GoldNotFoundError.
    """
    from app.domain.context.service import get_context

    get_context(db, project)
    gold_spec(settings, project, params.gold)


def validate_dry_run(
    db: Session, settings: Settings, project: Project, params: ContextDryRunParams, *, actor: User
) -> ContextDryRunParams:
    """Al encolar la clasificación de prueba: referencia, Markdown vigente de la plantilla o del manifiesto (lo fija la
    API, como en ``context_build``) e IA configurada si se pide.

    Raises:
        GoldNotFoundError, InvalidContextBuildError, AiNotConfiguredError.
    """
    from app.domain.ai import settings as ai_settings
    from app.domain.context import templates
    from app.domain.context.errors import InvalidContextBuildError, TemplateNotFoundError
    from app.domain.context.service import read_manifest

    gold_spec(settings, project, params.gold)
    if params.catalog == "template" and params.template_name is not None:
        try:
            markdown = templates.template_markdown(db, actor, params.template_name)
        except TemplateNotFoundError:
            raise InvalidContextBuildError(f"No existe la plantilla «{params.template_name}».") from None
    else:
        manifest = read_manifest(settings, project)
        if manifest.markdown is None or manifest.error:
            raise InvalidContextBuildError(manifest.error or "El proyecto no tiene manifiesto de taxonomía.")
        markdown = manifest.markdown
    if params.ai_scope != "off":
        ai_settings.require_configured(db, settings, "litellm")
    return params.model_copy(update={"template_markdown": markdown})


def validate_taxonomy_agent(
    db: Session, settings: Settings, project: Project, params: TaxonomyAgentParams, *, actor: User
) -> TaxonomyAgentParams:
    """Al encolar el diseñador: IA configurada y el Markdown vigente del manifiesto o la plantilla de partida.

    Raises:
        AiNotConfiguredError, InvalidContextBuildError.
    """
    from app.domain.ai import settings as ai_settings
    from app.domain.context import templates
    from app.domain.context.errors import InvalidContextBuildError, TemplateNotFoundError
    from app.domain.context.service import read_manifest

    ai_settings.require_configured(db, settings, "litellm")  # tarea ``agent``
    markdown: str | None = None
    if params.catalog == "template" and params.template_name is not None:
        try:
            markdown = templates.template_markdown(db, actor, params.template_name)
        except TemplateNotFoundError:
            raise InvalidContextBuildError(f"No existe la plantilla «{params.template_name}».") from None
    elif params.catalog == "manifest":
        manifest = read_manifest(settings, project)
        if manifest.markdown is None or manifest.error:
            raise InvalidContextBuildError(manifest.error or "El proyecto no tiene manifiesto de taxonomía.")
        markdown = manifest.markdown
    return params.model_copy(update={"template_markdown": markdown})


def validate_taxonomy_check(params: TaxonomyCheckParams) -> None:
    """Al encolar la comprobación por reglas: el Markdown es un manifiesto válido.

    Raises:
        TemplateInvalidError: No lo es.
    """
    from app.domain.context import templates

    templates.validate_markdown(params.markdown)


def validate_review_agent(db: Session, settings: Settings, project: Project) -> None:
    """Al encolar el revisor: contexto construido con ejes, destino de lectura y escritura (aceptar propuestas
    escribe decisiones) e IA configurada.

    Raises:
        ContextNotFoundError, InvalidContextBuildError, DestinationReadOnlyError, AiNotConfiguredError.
    """
    from app.domain.ai import settings as ai_settings
    from app.domain.context.errors import DestinationReadOnlyError, InvalidContextBuildError
    from app.domain.context.service import get_context

    row = get_context(db, project)
    if not row.taxonomy_axes or row.catalog_kind not in ("template", "manifest"):
        raise InvalidContextBuildError("El revisor necesita un contexto construido con plantilla o manifiesto.")
    if project.destination_location.access != "rw":
        raise DestinationReadOnlyError("La ubicación de destino es de solo lectura.")
    ai_settings.require_configured(db, settings, "litellm")  # tarea ``agent``


def validate_audit(db: Session, project: Project) -> None:
    """Al encolar el auditor: hay contexto construido.

    Raises:
        ContextNotFoundError.
    """
    from app.domain.context.service import get_context

    get_context(db, project)
