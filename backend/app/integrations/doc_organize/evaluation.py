"""Calidad de la clasificación (W5, doc_organize 2.0 G3): referencia, evaluación y clasificación de prueba.

Firmas verificadas en el tag ``v2.0.0rc2``::

    load_gold_xlsx(path, *, columns=None, sheet="Referencia", document_column="documento") -> GoldStandard
    gold_from_decisions(decisions) -> GoldStandard
    evaluate_classification(context, gold, *, roots=None) -> EvaluationReport
    dry_run_classify(project, documents, *, gold=None, only_gold=True, roots=None, builder=None, ai_cache=False,
        **build_options) -> DryRunResult(context, evaluation, documents)

Las claves de los documentos son las de las decisiones: ruta relativa a la raíz de la ubicación de origen
(``scan_roots``). La evaluación y la clasificación de prueba solo se llaman desde el subproceso de un job; leer el
Excel de la referencia (``openpyxl``, sin docling) también desde la API, al subirlo. doc_organize se importa dentro de
cada función (G15).
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Final, Literal

from app.integrations.doc_organize.ai import AiConnection, build_limits, llm_client
from app.integrations.doc_organize.context import (
    CANCEL_POLL_SECONDS,
    TEMPLATE_SOURCE,
    SourceFolder,
    TemplateInvalidError,
    _project,
    converted_documents,
    scan_roots,
)
from app.integrations.doc_organize.projects import DocOrganizeOperationError

GoldSource = Literal["xlsx", "decisions"]
#: Documentos de la referencia que no están en el contexto que se devuelven (el total va aparte).
MAX_MISSING_SHOWN: Final = 50
DEFAULT_SHEET: Final = "Referencia"
DEFAULT_DOCUMENT_COLUMN: Final = "documento"


class GoldInvalidError(Exception):
    """La referencia no se puede leer (hoja o columna que no existen, fichero que no es un Excel…)."""


@dataclass(frozen=True)
class GoldSpec:
    """De dónde sale la referencia: un Excel (con su hoja y sus columnas) o las decisiones del proyecto."""

    source: GoldSource
    path: Path | None = None
    sheet: str = DEFAULT_SHEET
    document_column: str = DEFAULT_DOCUMENT_COLUMN
    columns: dict[str, str] | None = None


@dataclass(frozen=True)
class GoldSummary:
    labels: int
    axes: list[str]


def _load_gold(spec: GoldSpec, output_root: Path) -> Any:
    from doc_organize import ClassificationDecisionStore, gold_from_decisions, load_gold_xlsx

    if spec.source == "decisions":
        return gold_from_decisions(asyncio.run(ClassificationDecisionStore(output_root).load()))
    if spec.path is None:
        raise GoldInvalidError("No hay referencia en Excel.")
    try:
        return load_gold_xlsx(
            spec.path, columns=spec.columns or None, sheet=spec.sheet, document_column=spec.document_column
        )
    except (ValueError, KeyError, OSError) as exc:
        raise GoldInvalidError(str(exc)) from None
    except Exception as exc:  # noqa: BLE001 - openpyxl lanza sus propias excepciones con un fichero que no es Excel
        raise GoldInvalidError(f"No es un Excel válido ({type(exc).__name__}).") from None


def read_gold(spec: GoldSpec) -> GoldSummary:
    """Comprueba un Excel de referencia: cuántos documentos etiquetados y en qué ejes.

    Raises:
        GoldInvalidError: No se puede leer.
    """
    gold = _load_gold(spec, Path("."))
    axes = sorted({axis for label in gold.labels for axis in label.axes})
    return GoldSummary(labels=len(gold.labels), axes=axes)


def _report(report: Any) -> dict[str, Any]:
    """``EvaluationReport`` en JSON, con como mucho ``MAX_MISSING_SHOWN`` documentos ausentes (y su total)."""
    data: dict[str, Any] = report.model_dump(mode="json")
    missing = data.get("missing_documents") or []
    data["missing_total"] = len(missing)
    data["missing_documents"] = missing[:MAX_MISSING_SHOWN]
    return data


def evaluate(
    output_root: Path, folders: list[SourceFolder], gold: GoldSpec, *, name: str, created_at: datetime
) -> dict[str, Any]:
    """Evalúa el contexto guardado (``context.json``) contra la referencia.

    Raises:
        GoldInvalidError: La referencia no se puede leer o está vacía.
        DocOrganizeOperationError: No hay contexto o no se pudo leer.
    """
    from doc_organize import ContextError, ContextRegistry, DocOrganizeError, evaluate_classification

    gold_standard = _load_gold(gold, output_root)
    if not gold_standard.labels:
        raise GoldInvalidError("La referencia no tiene ningún documento etiquetado.")
    try:
        context = asyncio.run(ContextRegistry().load_context(_project(name, output_root, created_at)))
    except (ContextError, DocOrganizeError, OSError, ValueError) as exc:
        raise DocOrganizeOperationError("No se pudo leer el contexto del proyecto.") from exc
    return _report(evaluate_classification(context, gold_standard, roots=scan_roots(folders)))


@dataclass(frozen=True)
class DryRunRequest:
    """Una clasificación de prueba: la configuración «candidata» que se compara con el contexto actual.

    Attributes:
        manifest_markdown: Plantilla o manifiesto con el que clasificar (``None`` = sin catálogo de ejes).
        ai: Conexión de la familia ``litellm`` (``None`` = sin IA).
        ai_scope: Alcance de la IA.
        profile_markdown: Perfil del proyecto que sustituye al guardado (``None`` = el guardado).
    """

    name: str
    created_at: datetime
    output_root: Path
    folders: list[SourceFolder]
    gold: GoldSpec
    manifest_markdown: str | None = None
    template_name: str | None = None
    candidate_domains: list[str] | None = None
    threshold: float = 0.5
    ai: AiConnection | None = None
    ai_scope: str = "off"
    profile_markdown: str | None = None
    versions: str = "all"
    version_across_extensions: bool = False


#: Cambios por documento que se guardan en el resultado del run (el total va aparte).
MAX_CHANGES = 200


def dry_run(
    request: DryRunRequest,
    *,
    on_progress: Callable[[str, int, int | None], None],
    is_cancelled: Callable[[], bool],
) -> dict[str, Any] | None:
    """Clasifica con la configuración candidata los documentos de la referencia, sin guardar nada, y la compara con la
    evaluación del contexto actual. ``None`` si se canceló.

    Raises:
        GoldInvalidError, TemplateInvalidError, DocOrganizeOperationError.
    """
    from doc_organize import (
        CancelToken,
        ContextError,
        ContextRegistry,
        DocOrganizeError,
        OperationCancelledError,
        TaxonomyTemplateError,
        compose_profile,
        compose_profile_text,
        dry_run_classify,
        evaluate_classification,
        parse_taxonomy_template,
    )

    gold = _load_gold(request.gold, request.output_root)
    if not gold.labels:
        raise GoldInvalidError("La referencia no tiene ningún documento etiquetado.")
    roots = scan_roots(request.folders)
    project = _project(request.name, request.output_root, request.created_at)
    baseline: dict[str, Any] | None = None
    current: Any = None
    try:
        current = asyncio.run(ContextRegistry().load_context(project))
        baseline = _report(evaluate_classification(current, gold, roots=roots))
    except (ContextError, OSError, ValueError):
        baseline = None  # sin contexto construido, solo la candidata
    manifest = None
    if request.manifest_markdown is not None:
        try:
            manifest = parse_taxonomy_template(request.manifest_markdown, source=TEMPLATE_SOURCE)
        except TaxonomyTemplateError as exc:
            raise TemplateInvalidError(str(exc)) from None
    profile = None
    if request.profile_markdown is not None:
        profile = compose_profile_text(manifest.profile if manifest is not None else None, request.profile_markdown)
    elif manifest is not None:
        profile = compose_profile(manifest.profile, request.output_root)
    documents, _ = converted_documents(request.folders)
    token = CancelToken()
    stop = threading.Event()

    def _bridge() -> None:
        while not stop.wait(CANCEL_POLL_SECONDS):
            if is_cancelled():
                token.cancel()
                return

    def _ai_progress(event: Any) -> None:
        on_progress("quality_ai", int(event.processed), int(event.total) if event.total else None)

    async def _run() -> Any:
        options: dict[str, Any] = {
            "gold": gold,
            "roots": roots,
            "candidate_domains": request.candidate_domains,
            "threshold": request.threshold,
            "taxonomy_manifest": manifest,
            "taxonomy_template_name": request.template_name if manifest is not None else None,
            "versions": request.versions,
            "version_across_extensions": request.version_across_extensions,
            "cancel_token": token,
            "on_progress": _ai_progress,
        }
        if current is not None:
            options["baseline"] = current  # rc2: qué documentos cambian de valor y en qué eje
        if profile is not None:
            options["profile"] = profile
        if request.ai is None or request.ai_scope == "off":
            return await dry_run_classify(project, documents, **options)
        options |= {"ai_scope": request.ai_scope, **build_limits(request.ai, ["classify"])}
        async with llm_client(request.ai) as llm:
            return await dry_run_classify(project, documents, llm=llm, **options)

    watcher = threading.Thread(target=_bridge, name="dow-dry-run-cancel", daemon=True)
    watcher.start()
    on_progress("quality_classify", 0, None)
    try:
        result = asyncio.run(_run())
    except OperationCancelledError:
        return None
    except (DocOrganizeError, OSError) as exc:
        raise DocOrganizeOperationError("doc_organize no pudo hacer la clasificación de prueba.") from exc
    finally:
        stop.set()
    stats = result.context.ai_stats.classification
    changes = list(result.changes or [])
    return {
        "baseline": baseline,
        "changes_total": len(changes),
        "changes": [
            {
                "document_key": change.document_key,
                "axis": change.axis,
                "before": list(change.before),
                "after": list(change.after),
                "before_by": change.before_by,
                "after_by": change.after_by,
            }
            for change in changes[:MAX_CHANGES]
        ],
        "candidate": _report(result.evaluation) if result.evaluation is not None else None,
        "documents": int(result.documents),
        "ai": {
            "scope": str(result.context.ai_stats.scope),
            "calls": int(stats.sent),
            "failed": int(stats.failed),
            "stopped": stats.stopped,
            "prompt_tokens": int(stats.prompt_tokens),
            "completion_tokens": int(stats.completion_tokens),
            "model": result.context.model_for_task("classify"),
        },
    }
