"""Resultados de las ejecuciones (``runs.result``) como modelos Pydantic, uno por operación (3.0, PR 3a).

Las operaciones construyen su modelo y el runner lo guarda con :meth:`RunResult.stored`; lo que llega a la BD es lo
mismo que antes de tiparlos:

- todos los campos son opcionales: un run fallido o cancelado guarda un resultado parcial y hay resultados históricos
  con otra forma;
- ``extra="allow"``: una clave que el modelo no declara (de versiones anteriores, como ``collisions``) no se pierde;
- se guarda con ``exclude_unset``: solo las claves que la operación escribió, también las que escribió con ``None``
  (``fuzzy_threshold``, ``output_files`` sin borrar salidas…). El orden de los campos de cada modelo es el orden en que
  la operación los escribe: la vista genérica de resultados los muestra en ese orden.

Desde el PR 3b la API devuelve estos modelos (``RunOut`` es una unión discriminada por ``operation``) y se serializan
siempre como se guardaron: solo las claves escritas (y las desconocidas), nunca un ``null`` por cada campo que la
operación no escribió. Los informes que vienen de doc_organize (evaluación, comprobación por reglas
y auditor) declaran los campos verificados en doc_organize 2.5.0; el resto de sus claves se conserva
(``extra="allow"``).

Para leer un resultado guardado: :func:`parse_result` (por operación) o :func:`parse_result_as` (con el modelo). Si no
valida, se registra con el id de la ejecución (sin valores) y devuelven ``None``.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field, SerializerFunctionWrapHandler, ValidationError, model_serializer
from pydantic.json_schema import SkipJsonSchema

logger = logging.getLogger(__name__)

#: Clave interna de ``runs.result`` con lo necesario para retomar un escaneo en otro tramo (G38); no es resultado.
RESUME_KEY: Final = "resume"


class _Open(BaseModel):
    """Base de los resultados y de sus partes: campos opcionales y claves desconocidas conservadas."""

    model_config = ConfigDict(extra="allow")

    # Sin anotación de retorno a propósito: con ella, el esquema de serialización (OpenAPI) sería ese tipo y no el del
    # modelo.
    @model_serializer(mode="wrap")
    def _only_written(self, handler: SerializerFunctionWrapHandler):  # type: ignore[no-untyped-def]
        """Solo las claves escritas (``model_fields_set``) y las desconocidas: la forma guardada."""
        data = handler(self)
        written = self.model_fields_set | set(self.model_extra or {})
        return {key: value for key, value in data.items() if key in written}


class RunResult(_Open):
    """Resultado de una ejecución."""

    def stored(self) -> dict[str, Any]:
        """El resultado tal como se guarda en ``runs.result``: solo lo que se escribió, en JSON."""
        return self.model_dump(mode="json", exclude_unset=True)


# --- motor y operaciones de proyecto -------------------------------------------------------------------------------


class NoopResult(RunResult):
    steps: int | None = None


class HistoryClearResult(RunResult):
    output_files: int | None = None
    output_bytes: int | None = None
    state_files: int | None = None
    state_bytes: int | None = None


class ProjectDeleteResult(RunResult):
    """``output_files``/``output_bytes`` se guardan como ``None`` cuando no se borran las salidas."""

    delete_outputs: bool | None = None
    output_files: int | None = None
    output_bytes: int | None = None
    state_files: int | None = None
    state_bytes: int | None = None
    leftovers: int | None = None


class ProjectMoveResult(RunResult):
    files: int | None = None
    bytes: int | None = None
    same_filesystem: bool | None = None
    free_bytes: int | None = None
    destination_location: str | None = None
    destination_subpath: str | None = None
    leftovers: int | None = None


# --- escaneo ---------------------------------------------------------------------------------------------------------


class ScanResume(_Open):
    """Estado entre tramos de un escaneo (``runs.result["resume"]``)."""

    done: list[str] | None = None
    partial: str | None = None
    failed: list[str] | None = None


class ScanResult(RunResult):
    """Recuentos del escaneo o, con ``force`` y ``dry_run``, de su vista previa (``cached`` … ``output_bytes``).

    Los segundos pueden ser enteros (``0``) o decimales: ``int | float`` conserva el tipo guardado.
    """

    # Vista previa de «forzar reconversión».
    cached: int | None = None
    orphaned: int | None = None
    excluded: int | None = None
    output_files: int | None = None
    output_bytes: int | None = None
    # Escaneo.
    folders: int | None = None
    force: bool | None = None
    scanned: int | None = None
    new: int | None = None
    modified: int | None = None
    unchanged: int | None = None
    converted: int | None = None
    conversion_errors: int | None = None
    ocr_required: int | None = None
    ocr_processed: int | None = None
    error_retries: int | None = None
    error_retries_capped: int | None = None
    io_errors: int | None = None
    excluded_cached: int | None = None
    duration_seconds: int | float | None = None
    discovery_duration_seconds: int | float | None = None
    total_conversion_seconds: int | float | None = None
    errors: int | None = None
    warnings: int | None = None
    event_schema_version: int | None = None
    segments: int | None = None
    search_indexed: int | None = None
    failed_folders: int | None = None
    # Estado interno (no es resultado): fuera del esquema OpenAPI; la API lo quita antes de leer el resultado.
    resume: SkipJsonSchema[ScanResume | None] = None


# --- exportaciones y entrega ----------------------------------------------------------------------------------------


class ExportZipResult(RunResult):
    file_count: int | None = None
    total_size_bytes: int | None = None
    size_bytes: int | None = None


class ExportXlsxResult(RunResult):
    rows: int | None = None
    size_bytes: int | None = None


class ExportSiteResult(RunResult):
    sha256: str | None = None
    zip_size_bytes: int | None = None
    file_count: int | None = None
    total_size_bytes: int | None = None
    neutralized_items: int | None = None
    neutralized_pages: int | None = None
    credentials_redacted: int | None = None
    search_excluded: int | None = None
    llms_txt: bool | None = None
    file_name: str | None = None
    redact_credentials: bool | None = None


class ExportAiBundleResult(RunResult):
    """Estadísticas de ``write_ai_context_bundle``, el fichero y las opciones con que se pidió."""

    file_count: int | None = None
    total_size_bytes: int | None = None
    documents: int | None = None
    superseded_skipped: int | None = None
    missing_text: int | None = None
    redacted_documents: int | None = None
    full_text_truncated: bool | None = None
    sha256: str | None = None
    file_name: str | None = None
    zip_size_bytes: int | None = None
    include_text: bool | None = None
    current_only: bool | None = None
    redact: bool | None = None
    max_file_chars: int | None = None
    max_full_chars: int | None = None


class SearchIndexResult(RunResult):
    indexed: int | None = None
    added: int | None = None
    updated: int | None = None
    removed: int | None = None


# --- duplicados ------------------------------------------------------------------------------------------------------


class DedupPreviewResult(RunResult):
    """``content_*`` solo con la búsqueda por contenido; ``semantic_*``, ``embedded`` y ``reused``, con la semántica."""

    documents: int | None = None
    groups: int | None = None
    exact_groups: int | None = None
    version_groups: int | None = None
    fuzzy_groups: int | None = None
    duplicate_files: int | None = None
    reclaimable_bytes: int | None = None
    stale_cache: int | None = None
    excluded: int | None = None
    fuzzy_threshold: int | None = None
    content_groups: int | None = None
    content_compared: int | None = None
    content_not_compared: int | None = None
    semantic_groups: int | None = None
    semantic_threshold: float | None = None
    embedded: int | None = None
    reused: int | None = None


class DedupApplyResult(RunResult):
    """Vista previa: ``files``, ``bytes`` y ``skipped_changed``; ejecución real: ``processed`` … ``skipped_changed``."""

    mode: str | None = None
    groups: int | None = None
    files: int | None = None
    bytes: int | None = None
    processed: int | None = None
    failed: int | None = None
    failed_paths: list[str] | None = None
    groups_done: int | None = None
    skipped_changed: int | None = None


# --- contexto --------------------------------------------------------------------------------------------------------


class AiPhaseResult(_Open):
    """Una fase de IA de la construcción: ``classified`` y ``scope`` al clasificar, ``applied`` al describir.

    Sin la fase, solo ``{"enabled": false}``.
    """

    enabled: bool | None = None
    calls: int | None = None
    failed: int | None = None
    stopped: str | None = None
    cached: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    response_format: str | None = None
    classified: int | None = None
    applied: int | None = None
    scope: str | None = None
    model: str | None = None


class SemanticResult(_Open):
    """Sub-fase semántica (W6) de la construcción; sin ella, ``{"enabled": false}``."""

    enabled: bool | None = None
    embedded: int | None = None
    cached: int | None = None
    assigned: int | None = None
    failed: int | None = None
    prompt_tokens: int | None = None
    model: str | None = None
    index_vectors: int | None = None
    index_bytes: int | None = None


class ContextBuildResult(RunResult):
    output_folder_name: str | None = None
    domains: int | None = None
    documents: int | None = None
    unclassified: int | None = None
    failed: int | None = None
    failed_paths: list[str] | None = None
    missing_originals: int | None = None
    site_built: bool | None = None
    ai: AiPhaseResult | None = None
    ai_enrichment: AiPhaseResult | None = None
    semantic: SemanticResult | None = None


class ContextDeleteResult(RunResult):
    output_folder_name: str | None = None
    files: int | None = None
    bytes: int | None = None


class CatalogEntry(_Open):
    slug: str | None = None
    name: str | None = None


class TaxonomyDraftResult(RunResult):
    manifest_markdown: str | None = None
    reasoning: str | None = None
    sample_documents: int | None = None
    total_documents: int | None = None
    domains: list[CatalogEntry] | None = None
    material_types: list[CatalogEntry] | None = None
    model: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    ai_cached: bool | None = None


# --- calidad ---------------------------------------------------------------------------------------------------------
# Informes de doc_organize 2.5.0 (``model_dump`` de sus modelos, con sus mismos valores por defecto):
# ``EvaluationReport``, ``AxisEvaluation`` y ``LabelConfusion`` (``context/evaluation.py``), ``DocumentChange``
# (``context/dry_run.py``), ``TaxonomyRulesReport``, ``AxisRulesReport`` y ``NearMiss`` (``context/taxonomy_check.py``)
# y ``TaxonomyAudit``, ``AxisAudit`` y ``AuditFinding`` (``context/review_agent.py``). Se serializan enteros (con los
# valores por defecto de lo que falte), como los da doc_organize; un informe que no valida deja el resultado en ``None``.


class _Report(BaseModel):
    """Base de los informes de doc_organize: las claves que la web no declara se conservan.

    Se serializan con todos sus campos, así que en el esquema de la respuesta (OpenAPI) son obligatorios.
    """

    model_config = ConfigDict(extra="allow", json_schema_serialization_defaults_required=True)


class LabelConfusion(_Report):
    """Un error frecuente: lo que decía la referencia y lo que se asignó."""

    label: str
    assigned: str
    count: int


class AxisEvaluation(_Report):
    """Métricas de un eje sobre los documentos etiquetados que están en el contexto."""

    axis: str
    multiple: bool = False
    labelled: int = 0
    accuracy: float | None = None
    coverage: float | None = None
    precision: float | None = None
    recall: float | None = None
    accuracy_by_classified_by: dict[str, float] = Field(default_factory=dict)
    labelled_by_classified_by: dict[str, int] = Field(default_factory=dict)
    confusions: list[LabelConfusion] = Field(default_factory=list)


class EvaluationReport(_Report):
    """Evaluación contra la referencia; la web recorta ``missing_documents`` y guarda su total en ``missing_total``."""

    axes: dict[str, AxisEvaluation] = Field(default_factory=dict)
    documents: int = 0
    matched: int = 0
    missing_documents: list[str] = Field(default_factory=list)
    missing_total: int | None = None


class DocumentChange(_Report):
    """Un documento que cambia de valor en un eje en la clasificación de prueba."""

    document_key: str
    axis: str
    before: list[str]
    after: list[str]
    before_by: str | None = None
    after_by: str | None = None


class ContextEvaluateResult(RunResult):
    gold: str | None = None
    report: EvaluationReport | None = None


class DryRunAiResult(_Open):
    scope: str | None = None
    calls: int | None = None
    failed: int | None = None
    stopped: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    model: str | None = None


class ContextDryRunResult(RunResult):
    baseline: EvaluationReport | None = None
    changes_total: int | None = None
    changes: list[DocumentChange] | None = None
    candidate: EvaluationReport | None = None
    documents: int | None = None
    ai: DryRunAiResult | None = None
    gold: str | None = None
    catalog: str | None = None
    template_name: str | None = None
    ai_scope: str | None = None
    profile_changed: bool | None = None


# --- agentes ---------------------------------------------------------------------------------------------------------


class NearMiss(_Report):
    """La entrada que más se acercó al umbral en un documento sin valor."""

    slug: str
    score: float
    matched: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)


class AxisRulesReport(_Report):
    """Comprobación por reglas de un eje (``coverage`` es un campo calculado de doc_organize)."""

    axis: str
    organizes: str | None = None
    documents: int = 0
    covered: int = 0
    conflicts: int = 0
    entry_counts: dict[str, int] = Field(default_factory=dict)
    empty_entries: list[str] = Field(default_factory=list)
    shared_terms: dict[str, list[str]] = Field(default_factory=dict)
    unused_keywords: dict[str, list[str]] = Field(default_factory=dict)
    uncovered_examples: list[str] = Field(default_factory=list)
    conflict_examples: dict[str, list[str]] = Field(default_factory=dict)
    conflict_terms: dict[str, dict[str, list[str]]] = Field(default_factory=dict)
    near_misses: dict[str, NearMiss] = Field(default_factory=dict)
    coverage: float = 0.0


class TaxonomyRulesReport(_Report):
    """Comprobación de un manifiesto por reglas; ``markdown`` es su tabla (``to_markdown``, la añade la web)."""

    axes: list[AxisRulesReport] = Field(default_factory=list)
    documents: int = 0
    unreadable: int = 0
    markdown: str | None = None


class _AgentRunResult(RunResult):
    """Recuentos comunes de una ejecución de un agente (``AgentRun``), en el orden en que se guardan."""

    stop_reason: str | None = None
    finished: bool | None = None
    steps: int | None = None
    tool_calls: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    tokens_estimated: bool | None = None
    duration_s: float | None = None


class TaxonomyAgentResult(_AgentRunResult):
    model: str | None = None
    base: bool | None = None
    instructions: bool | None = None
    max_steps: int | None = None
    documents: int | None = None
    improves: bool | None = None
    rationale: str | None = None
    edits: int | None = None
    markdown: str | None = None
    draft_markdown: str | None = None
    best_markdown: str | None = None
    base_report: TaxonomyRulesReport | None = None
    report: TaxonomyRulesReport | None = None
    best_report: TaxonomyRulesReport | None = None
    catalog: str | None = None
    template_name: str | None = None


class ContextReviewAgentResult(_AgentRunResult):
    """``proposals`` es el número de propuestas guardadas (no está si se canceló)."""

    model: str | None = None
    max_steps: int | None = None
    max_items: int | None = None
    reviewed: int | None = None
    summary: str | None = None
    proposals: int | None = None


class TaxonomyCheckResult(RunResult):
    report: TaxonomyRulesReport | None = None


class AxisAudit(_Report):
    axis: str
    documents: int = 0
    with_value: int = 0
    value_counts: dict[str, int] = Field(default_factory=dict)
    classified_by: dict[str, int] = Field(default_factory=dict)
    low_confidence: int = 0
    unverified_evidence: int = 0


class AuditFinding(_Report):
    """Qué revisar del catálogo: ``kind`` es un ``AuditFindingKind`` de doc_organize (``empty_entry``…)."""

    kind: str
    axis: str | None = None
    values: list[str] = Field(default_factory=list)
    count: int = 0
    message: str


class TaxonomyAudit(_Report):
    """Informe del auditor; ``markdown`` es su resumen (``to_markdown``, lo añade la web)."""

    documents: int = 0
    unclassified: int = 0
    axes: list[AxisAudit] = Field(default_factory=list)
    findings: list[AuditFinding] = Field(default_factory=list)
    markdown: str | None = None


class ContextAuditResult(RunResult):
    audit: TaxonomyAudit | None = None


#: Modelo del resultado de cada operación (las mismas claves que ``OPERATIONS``).
RESULT_MODELS: Final[dict[str, type[RunResult]]] = {
    "noop": NoopResult,
    "history_clear": HistoryClearResult,
    "project_move": ProjectMoveResult,
    "project_delete": ProjectDeleteResult,
    "scan": ScanResult,
    "export_zip": ExportZipResult,
    "export_xlsx": ExportXlsxResult,
    "export_site": ExportSiteResult,
    "export_ai_bundle": ExportAiBundleResult,
    "search_index": SearchIndexResult,
    "dedup_preview": DedupPreviewResult,
    "dedup_apply": DedupApplyResult,
    "context_build": ContextBuildResult,
    "context_delete": ContextDeleteResult,
    "taxonomy_draft": TaxonomyDraftResult,
    "context_evaluate": ContextEvaluateResult,
    "context_dry_run": ContextDryRunResult,
    "taxonomy_agent": TaxonomyAgentResult,
    "taxonomy_check": TaxonomyCheckResult,
    "context_review_agent": ContextReviewAgentResult,
    "context_audit": ContextAuditResult,
}


def parse_result_as[ResultT: RunResult](
    model: type[ResultT], data: object, *, run_id: str | None = None
) -> ResultT | None:
    """``data`` (un ``runs.result`` guardado) como ``model``; ``None`` si no hay resultado o no valida.

    Un resultado que no valida se registra con el id de la ejecución y el número de errores, nunca con sus valores.
    """
    if data is None:
        return None
    if not isinstance(data, Mapping):
        logger.warning("Resultado de ejecución que no es un objeto", extra={"run_id": run_id, "model": model.__name__})
        return None
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        logger.warning(
            "Resultado de ejecución con una forma no válida",
            extra={"run_id": run_id, "model": model.__name__, "errors": exc.error_count()},
        )
        return None


def parse_result(operation: str, data: object, *, run_id: str | None = None) -> RunResult | None:
    """``data`` como el resultado de ``operation`` (:func:`parse_result_as`); ``None`` también si la operación no
    existe."""
    model = RESULT_MODELS.get(operation)
    if model is None:
        if data is not None:
            logger.warning("Resultado de una operación desconocida", extra={"run_id": run_id, "operation": operation})
        return None
    return parse_result_as(model, data, run_id=run_id)
