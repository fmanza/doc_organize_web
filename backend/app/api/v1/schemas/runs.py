"""Ejecuciones (cola, progreso y resultados)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel
from pydantic.json_schema import SkipJsonSchema

from app.api.v1.schemas._common import _Out
from app.api.v1.schemas.projects import Operation, RunStatus
from app.domain.runs.operations import (
    ContextAuditParams,
    ContextBuildParams,
    ContextDeleteParams,
    ContextDryRunParams,
    ContextEvaluateParams,
    ContextReviewAgentParams,
    DedupPreviewParams,
    ExclusionSnapshot,
    ExportAiBundleParams,
    ExportSiteParams,
    ExportXlsxParams,
    ExportZipParams,
    HistoryClearParams,
    NoopParams,
    ProjectDeleteParams,
    ProjectMoveParams,
    ScanParams,
    SearchIndexParams,
    TaxonomyAgentParams,
    TaxonomyDraftParams,
)
from app.domain.runs.results import (
    ContextAuditResult,
    ContextBuildResult,
    ContextDeleteResult,
    ContextDryRunResult,
    ContextEvaluateResult,
    ContextReviewAgentResult,
    DedupApplyResult,
    DedupPreviewResult,
    ExportAiBundleResult,
    ExportSiteResult,
    ExportXlsxResult,
    ExportZipResult,
    HistoryClearResult,
    NoopResult,
    ProjectDeleteResult,
    ProjectMoveResult,
    RunResult,
    ScanResult,
    SearchIndexResult,
    TaxonomyAgentResult,
    TaxonomyCheckResult,
    TaxonomyDraftResult,
)


class ArtifactOut(_Out):
    """Fichero de un run, descargable mientras no lo purgue la retención."""

    id: int
    name: str
    kind: Literal["log", "output", "report"]
    size_bytes: int
    content_type: str
    created_at: datetime


class RunProgress(BaseModel):
    """Último progreso publicado."""

    phase: str
    processed: int
    total: int | None = None
    current: str | None = None


class ContextLeftoverOut(BaseModel):
    """Contexto que quedó en disco sin guardarse (construcción interrumpida, 2.1), o ninguno."""

    output_folder_name: str | None = Field(
        description="Carpeta reorganizada del context.json que hay en el destino; null si no hay restos"
    )


class AiUsageRowOut(BaseModel):
    """Consumo de IA de una ejecución en una tarea (web 2.1). Sin coste: el proxy no lo da por llamada."""

    task: str
    model: str | None
    calls: int = Field(description="Documentos enviados (pasos, en los agentes; textos embebidos, en embed)")
    cached: int = Field(description="Resueltos con la caché de resultados de IA, sin llamar al modelo")
    failed: int
    prompt_tokens: int
    completion_tokens: int
    tokens_estimated: bool = Field(description="Tokens estimados (agentes, si el proxy no los informa)")


# --- parámetros devueltos -------------------------------------------------------------------------------------------
# Los de cada operación tal como se guardaron, sin lo que no se devuelve (``public_params``): mismos campos que al
# encolar, más los que copia la API (``capture_owner``, ``exclusion``) y las claves de versiones anteriores
# (``extra="allow"``). Si unos parámetros guardados ya no validan, se devuelven tal cual (``params_out``).

_OUT_CONFIG: Final = ConfigDict(extra="allow")
#: Campo guardado que no se devuelve (``HIDDEN_PARAMS``): ni en el esquema ni en el JSON.
_Hidden = Annotated[SkipJsonSchema[str | None], Field(exclude=True)]


class NoopParamsOut(NoopParams):
    model_config = _OUT_CONFIG


class HistoryClearParamsOut(HistoryClearParams):
    model_config = _OUT_CONFIG


class ProjectMoveParamsOut(ProjectMoveParams):
    model_config = _OUT_CONFIG


class ProjectDeleteParamsOut(ProjectDeleteParams):
    model_config = _OUT_CONFIG


class ScanParamsOut(ScanParams):
    model_config = _OUT_CONFIG

    capture_owner: bool = Field(default=False, description="Se guardó la cuenta propietaria de cada fichero (1.5.0)")


class ExportZipParamsOut(ExportZipParams):
    model_config = _OUT_CONFIG


class ExportXlsxParamsOut(ExportXlsxParams):
    model_config = _OUT_CONFIG


class ExportSiteParamsOut(ExportSiteParams):
    model_config = _OUT_CONFIG


class ExportAiBundleParamsOut(ExportAiBundleParams):
    model_config = _OUT_CONFIG


class SearchIndexParamsOut(SearchIndexParams):
    model_config = _OUT_CONFIG


class DedupPreviewParamsOut(DedupPreviewParams):
    model_config = _OUT_CONFIG

    exclusion: ExclusionSnapshot | None = Field(default=None, description="Exclusión efectiva copiada al encolar (2.7)")


class DedupApplyParamsOut(BaseModel):
    """Parámetros de ``dedup_apply``: los grupos confirmados se devuelven como su número."""

    model_config = _OUT_CONFIG

    operation: Literal["dedup_apply"] = "dedup_apply"
    groups_run_id: str
    mode: Literal["move", "copy", "report_only"] = "copy"
    groups: int = Field(description="Grupos confirmados (la lista no se devuelve)")
    dry_run: bool = True
    preview_run_id: str | None = None
    confirm_name: str | None = None


class ContextBuildParamsOut(ContextBuildParams):
    model_config = _OUT_CONFIG

    template_markdown: _Hidden = None


class ContextDeleteParamsOut(ContextDeleteParams):
    model_config = _OUT_CONFIG


class TaxonomyDraftParamsOut(TaxonomyDraftParams):
    model_config = _OUT_CONFIG


class ContextEvaluateParamsOut(ContextEvaluateParams):
    model_config = _OUT_CONFIG


class ContextDryRunParamsOut(ContextDryRunParams):
    model_config = _OUT_CONFIG

    template_markdown: _Hidden = None
    profile_markdown: _Hidden = None


class TaxonomyAgentParamsOut(TaxonomyAgentParams):
    model_config = _OUT_CONFIG

    template_markdown: _Hidden = None


class TaxonomyCheckParamsOut(BaseModel):
    """Parámetros de ``taxonomy_check``: el manifiesto comprobado no se devuelve."""

    model_config = _OUT_CONFIG

    operation: Literal["taxonomy_check"] = "taxonomy_check"


class ContextReviewAgentParamsOut(ContextReviewAgentParams):
    model_config = _OUT_CONFIG


class ContextAuditParamsOut(ContextAuditParams):
    model_config = _OUT_CONFIG


#: Modelo de los parámetros devueltos de cada operación.
PARAMS_OUT_MODELS: Final[dict[str, type[BaseModel]]] = {
    "noop": NoopParamsOut,
    "history_clear": HistoryClearParamsOut,
    "project_move": ProjectMoveParamsOut,
    "project_delete": ProjectDeleteParamsOut,
    "scan": ScanParamsOut,
    "export_zip": ExportZipParamsOut,
    "export_xlsx": ExportXlsxParamsOut,
    "export_site": ExportSiteParamsOut,
    "export_ai_bundle": ExportAiBundleParamsOut,
    "search_index": SearchIndexParamsOut,
    "dedup_preview": DedupPreviewParamsOut,
    "dedup_apply": DedupApplyParamsOut,
    "context_build": ContextBuildParamsOut,
    "context_delete": ContextDeleteParamsOut,
    "taxonomy_draft": TaxonomyDraftParamsOut,
    "context_evaluate": ContextEvaluateParamsOut,
    "context_dry_run": ContextDryRunParamsOut,
    "taxonomy_agent": TaxonomyAgentParamsOut,
    "taxonomy_check": TaxonomyCheckParamsOut,
    "context_review_agent": ContextReviewAgentParamsOut,
    "context_audit": ContextAuditParamsOut,
}


class _RunOutBase(BaseModel):
    """Ejecución con su estado, progreso, resultado y artefactos (campos comunes a todas las operaciones)."""

    id: str
    project_id: int | None
    project_name: str | None
    operation: Operation
    queue: Literal["cpu", "gpu"]
    status: RunStatus
    is_write: bool
    params: BaseModel
    progress: RunProgress | None
    result: RunResult | None = Field(
        description="Resultado de la operación; null si no hay o si el guardado no tiene una forma válida"
    )
    error_code: str | None
    error_message: str | None
    cancel_requested: bool
    created_by_username: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    workspace_purged: bool
    artifacts: list[ArtifactOut]
    can_cancel: bool
    ai_usage: list[AiUsageRowOut] = Field(
        default_factory=list, description="Consumo de IA por tarea (solo en el detalle de una ejecución; 2.1)"
    )


class NoopRunOut(_RunOutBase):
    operation: Literal["noop"]
    params: NoopParamsOut
    result: NoopResult | None


class HistoryClearRunOut(_RunOutBase):
    operation: Literal["history_clear"]
    params: HistoryClearParamsOut
    result: HistoryClearResult | None


class ProjectMoveRunOut(_RunOutBase):
    operation: Literal["project_move"]
    params: ProjectMoveParamsOut
    result: ProjectMoveResult | None


class ProjectDeleteRunOut(_RunOutBase):
    operation: Literal["project_delete"]
    params: ProjectDeleteParamsOut
    result: ProjectDeleteResult | None


class ScanRunOut(_RunOutBase):
    operation: Literal["scan"]
    params: ScanParamsOut
    result: ScanResult | None


class ExportZipRunOut(_RunOutBase):
    operation: Literal["export_zip"]
    params: ExportZipParamsOut
    result: ExportZipResult | None


class ExportXlsxRunOut(_RunOutBase):
    operation: Literal["export_xlsx"]
    params: ExportXlsxParamsOut
    result: ExportXlsxResult | None


class ExportSiteRunOut(_RunOutBase):
    operation: Literal["export_site"]
    params: ExportSiteParamsOut
    result: ExportSiteResult | None


class ExportAiBundleRunOut(_RunOutBase):
    operation: Literal["export_ai_bundle"]
    params: ExportAiBundleParamsOut
    result: ExportAiBundleResult | None


class SearchIndexRunOut(_RunOutBase):
    operation: Literal["search_index"]
    params: SearchIndexParamsOut
    result: SearchIndexResult | None


class DedupPreviewRunOut(_RunOutBase):
    operation: Literal["dedup_preview"]
    params: DedupPreviewParamsOut
    result: DedupPreviewResult | None


class DedupApplyRunOut(_RunOutBase):
    operation: Literal["dedup_apply"]
    params: DedupApplyParamsOut
    result: DedupApplyResult | None


class ContextBuildRunOut(_RunOutBase):
    operation: Literal["context_build"]
    params: ContextBuildParamsOut
    result: ContextBuildResult | None


class ContextDeleteRunOut(_RunOutBase):
    operation: Literal["context_delete"]
    params: ContextDeleteParamsOut
    result: ContextDeleteResult | None


class TaxonomyDraftRunOut(_RunOutBase):
    operation: Literal["taxonomy_draft"]
    params: TaxonomyDraftParamsOut
    result: TaxonomyDraftResult | None


class ContextEvaluateRunOut(_RunOutBase):
    operation: Literal["context_evaluate"]
    params: ContextEvaluateParamsOut
    result: ContextEvaluateResult | None


class ContextDryRunRunOut(_RunOutBase):
    operation: Literal["context_dry_run"]
    params: ContextDryRunParamsOut
    result: ContextDryRunResult | None


class TaxonomyAgentRunOut(_RunOutBase):
    operation: Literal["taxonomy_agent"]
    params: TaxonomyAgentParamsOut
    result: TaxonomyAgentResult | None


class TaxonomyCheckRunOut(_RunOutBase):
    operation: Literal["taxonomy_check"]
    params: TaxonomyCheckParamsOut
    result: TaxonomyCheckResult | None


class ContextReviewAgentRunOut(_RunOutBase):
    operation: Literal["context_review_agent"]
    params: ContextReviewAgentParamsOut
    result: ContextReviewAgentResult | None


class ContextAuditRunOut(_RunOutBase):
    operation: Literal["context_audit"]
    params: ContextAuditParamsOut
    result: ContextAuditResult | None


#: Modelo de la respuesta de cada operación (las mismas claves que ``RESULT_MODELS``).
RUN_OUT_MODELS: Final[dict[str, type[_RunOutBase]]] = {
    "noop": NoopRunOut,
    "history_clear": HistoryClearRunOut,
    "project_move": ProjectMoveRunOut,
    "project_delete": ProjectDeleteRunOut,
    "scan": ScanRunOut,
    "export_zip": ExportZipRunOut,
    "export_xlsx": ExportXlsxRunOut,
    "export_site": ExportSiteRunOut,
    "export_ai_bundle": ExportAiBundleRunOut,
    "search_index": SearchIndexRunOut,
    "dedup_preview": DedupPreviewRunOut,
    "dedup_apply": DedupApplyRunOut,
    "context_build": ContextBuildRunOut,
    "context_delete": ContextDeleteRunOut,
    "taxonomy_draft": TaxonomyDraftRunOut,
    "context_evaluate": ContextEvaluateRunOut,
    "context_dry_run": ContextDryRunRunOut,
    "taxonomy_agent": TaxonomyAgentRunOut,
    "taxonomy_check": TaxonomyCheckRunOut,
    "context_review_agent": ContextReviewAgentRunOut,
    "context_audit": ContextAuditRunOut,
}

RunOutVariant = Annotated[
    NoopRunOut
    | HistoryClearRunOut
    | ProjectMoveRunOut
    | ProjectDeleteRunOut
    | ScanRunOut
    | ExportZipRunOut
    | ExportXlsxRunOut
    | ExportSiteRunOut
    | ExportAiBundleRunOut
    | SearchIndexRunOut
    | DedupPreviewRunOut
    | DedupApplyRunOut
    | ContextBuildRunOut
    | ContextDeleteRunOut
    | TaxonomyDraftRunOut
    | ContextEvaluateRunOut
    | ContextDryRunRunOut
    | TaxonomyAgentRunOut
    | TaxonomyCheckRunOut
    | ContextReviewAgentRunOut
    | ContextAuditRunOut,
    Field(discriminator="operation"),
]


class RunOut(RootModel[RunOutVariant]):
    """Ejecución con su estado, progreso, resultado y artefactos; ``params`` y ``result`` según ``operation`` (3.0)."""


class RunPage(BaseModel):
    """Página del historial de ejecuciones."""

    items: list[RunOut]
    total: int
