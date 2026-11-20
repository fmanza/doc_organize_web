"""Catálogo de operaciones: parámetros (validados con Pydantic en la API y otra vez en el worker), rol mínimo, cola y
si escriben en el proyecto.

Las operaciones que mueven o borran ficheros (regla 7) se lanzan primero con ``dry_run`` (vista previa, sin escritura)
y después con ``preview_run_id`` de esa vista previa y ``confirm_name`` igual al nombre del proyecto.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator
from pydantic.json_schema import SkipJsonSchema

from app.db.models import MemberRole, RunQueue

FolderName = Annotated[str, Field(min_length=1, max_length=120)]


class _Params(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NoopParams(_Params):
    """Prueba del motor: ``steps`` pasos de ``step_seconds`` con progreso; ``fail_at_step`` simula un fallo."""

    operation: Literal["noop"] = "noop"
    steps: int = Field(default=5, ge=1, le=100)
    step_seconds: float = Field(default=1.0, ge=0, le=10)
    fail_at_step: int | None = Field(default=None, ge=1, le=100)


class _Destructive(_Params):
    """Parámetros comunes de las operaciones con vista previa."""

    dry_run: bool = True
    preview_run_id: str | None = Field(default=None, max_length=36)
    confirm_name: str | None = Field(default=None, max_length=128)


class HistoryClearParams(_Destructive):
    """Vaciar el histórico: borra las salidas y el estado de doc_organize del proyecto."""

    operation: Literal["history_clear"] = "history_clear"


class ProjectMoveParams(_Destructive):
    """Mover la carpeta de salidas a ``destination_parent/new_folder`` de una ubicación destino ``rw``."""

    operation: Literal["project_move"] = "project_move"
    destination_location_id: int = Field(ge=1)
    destination_parent: str = Field(default="", max_length=4096)
    new_folder: FolderName


class ProjectDeleteParams(_Destructive):
    """Borrar el proyecto; con ``delete_outputs`` también su carpeta de salidas (el estado se borra siempre)."""

    operation: Literal["project_delete"] = "project_delete"
    delete_outputs: bool = False


class ScanParams(_Params):
    """Escanear y convertir carpetas de origen del proyecto (``ScanOptions`` de doc_organize, G13).

    ``folders`` vacío = todas las carpetas de origen. Con ``force`` (vacía la caché y **borra** las salidas de lo que
    ya no está en el origen) son obligatorias todas las carpetas, el rol ``owner`` y el patrón de vista previa
    (``dry_run``, ``preview_run_id``, ``confirm_name``); sin ``force`` no hay vista previa.

    ``exclusions`` (subcarpetas excluidas de cada carpeta, relativas a ella) e ``ignore_patterns`` (patrones de la
    ubicación de origen) los copia la API al encolar (el valor del cliente se descarta, 1.4.0): todos los tramos del
    run usan esa copia aunque se cambien después. Con ``force``, lo que cubren se borra como si ya no existiera.
    ``capture_owner`` (1.5.0) también lo copia la API, del ajuste del proyecto.
    """

    operation: Literal["scan"] = "scan"
    folders: list[Annotated[str, Field(max_length=4096)]] = Field(default_factory=list, max_length=20)
    exclusions: dict[
        Annotated[str, Field(max_length=4096)],
        Annotated[list[Annotated[str, Field(min_length=1, max_length=4096)]], Field(max_length=50)],
    ] = Field(default_factory=dict, max_length=20)
    ignore_patterns: list[Annotated[str, Field(min_length=1, max_length=64)]] = Field(
        default_factory=list, max_length=30
    )
    use_ocr: bool = True
    use_gpu: bool = False
    force: bool = False
    include_audio_video: bool = False
    extract_images: bool = False
    use_picture_description: bool = False
    # Fuera del esquema OpenAPI: lo pone la API y el cliente no tiene que mandarlo (si lo manda, se descarta).
    capture_owner: SkipJsonSchema[bool] = False
    dry_run: bool = False
    preview_run_id: str | None = Field(default=None, max_length=36)
    confirm_name: str | None = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def _preview_only_with_force(self) -> ScanParams:
        if self.dry_run and not self.force:
            raise ValueError("La vista previa solo existe para «forzar reconversión»")
        return self


class ExportZipParams(_Params):
    """ZIP del proyecto (``Conversión/`` y ``cache_export.json``); con ``dry_run``, solo su tamaño (vista previa).

    No mueve ni borra nada: la vista previa sirve para ver el tamaño antes de ocupar el workspace, no es obligatoria.
    """

    operation: Literal["export_zip"] = "export_zip"
    dry_run: bool = False


class ExportXlsxParams(_Params):
    """Excel de la caché (``cache``), de los errores de escaneo (``errors``, estado actual e histórico), del
    historial del contexto (``context_history``, 1.5.0: construcciones y cambios) o de los documentos del contexto con
    sus ejes (``context_documents``, 2.0: hojas «Documentos» y «Ejes»)."""

    operation: Literal["export_xlsx"] = "export_xlsx"
    kind: Literal["cache", "errors", "context_history", "context_documents"]


class ExportSiteParams(_Params):
    """Sitio del contexto sin conexión en un ZIP reproducible con su SHA-256 (W8, F3): se construye sobre una copia en
    el workspace (no toca el sitio que sirve la web), se comprueba con ``check_site_offline`` y se empaqueta con
    ``write_site_zip``. ``llms_txt`` añade el índice para IA en la raíz del sitio."""

    operation: Literal["export_site"] = "export_site"
    llms_txt: bool = False


class ExportAiBundleParams(_Params):
    """Paquete para IA del contexto (W8, F7: ``write_ai_context_bundle``): ``llms.txt``, un ``.md`` por documento con
    su ficha y ``context.json``. ``redact=False`` solo lo puede pedir un administrador de la instancia (S-F7-1)."""

    operation: Literal["export_ai_bundle"] = "export_ai_bundle"
    include_text: bool = True
    current_only: bool = True
    redact: bool = True
    max_file_chars: int | None = Field(default=None, ge=1_000, le=10_000_000)
    max_full_chars: int | None = Field(default=None, ge=1_000, le=100_000_000)


class DedupPreviewParams(_Params):
    """Vista previa de duplicados de todas las carpetas de origen (no toca ficheros).

    ``fuzzy_threshold`` (50–100) añade los grupos por nombre parecido (``WRatio`` de RapidFuzz) sobre lo que no sea
    duplicado exacto ni conflicto de versión.
    """

    operation: Literal["dedup_preview"] = "dedup_preview"
    fuzzy_threshold: int | None = Field(default=None, ge=50, le=100)


class DedupChoice(BaseModel):
    """Grupo confirmado y documento que se conserva (``<carpeta>/<ruta>`` tal como lo da la vista previa)."""

    model_config = ConfigDict(extra="forbid")

    group_id: str = Field(min_length=1, max_length=36)
    keep: str = Field(min_length=1, max_length=1024)


class DedupApplyParams(_Params):
    """Aplicar los grupos confirmados de una vista previa de duplicados (``groups_run_id``).

    ``mode``: ``move`` (saca los descartados del origen a ``duplicados/``), ``copy`` (los copia, sin tocar el origen) o
    ``report_only`` (solo el informe). La ejecución real exige su propia vista previa (``dry_run``) y el nombre del
    proyecto, como el resto de operaciones que escriben ficheros (regla 7).
    """

    operation: Literal["dedup_apply"] = "dedup_apply"
    groups_run_id: str = Field(min_length=1, max_length=36)
    mode: Literal["move", "copy", "report_only"] = "copy"
    groups: list[DedupChoice] = Field(min_length=1, max_length=10_000)
    dry_run: bool = True
    preview_run_id: str | None = Field(default=None, max_length=36)
    confirm_name: str | None = Field(default=None, max_length=128)


class SearchIndexParams(_Params):
    """Pone al día el índice de búsqueda de texto completo con el Markdown de ``Conversión/``."""

    operation: Literal["search_index"] = "search_index"


#: Tamaño máximo de una plantilla o manifiesto de taxonomía (Markdown).
MAX_TEMPLATE_BYTES: Final = 256 * 1024
TemplateName = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9-]*$")]


class ContextBuildParams(_Params):
    """Construir el contexto del proyecto: clasificar, copiar a la carpeta reorganizada y generar el sitio (L-8).

    ``catalog``: ``discover`` (dominios descubiertos), ``domains`` (catálogo propio en ``domains``, un eje),
    ``template`` (plantilla ``template_name``, dos ejes) o ``manifest`` (``taxonomy_manifest.md`` del proyecto).
    ``output_folder_name`` solo se elige en la primera construcción; después es el del contexto existente.
    ``template_markdown`` lo rellena la API al encolar con la versión vigente de la plantilla (el valor del cliente se
    descarta) y no se devuelve en el run.
    ``ai_classification`` envía a la IA lo que las reglas dejan sin clasificar (Fase 8; tarea ``classify`` de la familia
    ``litellm`` desde doc_organize 2.0, ``ai_scope="unclassified"``).
    ``ai_enrichment`` (1.5.0) pide a la IA (tarea ``enrich``) descripción y palabras clave de los documentos
    clasificados que no las declaran; tiene su propio presupuesto de documentos.
    """

    operation: Literal["context_build"] = "context_build"
    catalog: Literal["discover", "domains", "template", "manifest"] = "discover"
    domains: list[Annotated[str, Field(min_length=1, max_length=128)]] = Field(default_factory=list, max_length=100)
    template_name: TemplateName | None = None
    output_folder_name: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    threshold: float = Field(default=0.5, ge=0, le=1)
    build_site: bool = True
    ai_classification: bool = False
    ai_enrichment: bool = False
    template_markdown: str | None = Field(default=None, max_length=MAX_TEMPLATE_BYTES)

    @model_validator(mode="after")
    def _catalog_fields(self) -> ContextBuildParams:
        if self.catalog == "domains" and not self.domains:
            raise ValueError("Con un catálogo propio hay que indicar al menos un dominio")
        if self.catalog != "domains" and self.domains:
            raise ValueError("«domains» solo se usa con el catálogo propio")
        if (self.catalog == "template") != (self.template_name is not None):
            raise ValueError("«template_name» se indica solo, y siempre, con el catálogo «template»")
        return self


class ContextDeleteParams(_Destructive):
    """Borrar el contexto: carpeta reorganizada, ``context.json``, ``domains/`` y el sitio (no toca ``Conversión/``)."""

    operation: Literal["context_delete"] = "context_delete"


def context_ai_tasks(params: ContextBuildParams) -> list[Literal["classify", "enrich"]]:
    """Tareas de IA (doc_organize 2.0) que usa ``params``: clasificar y describir, cada una si se pidió."""
    tasks: list[Literal["classify", "enrich"]] = []
    if params.ai_classification:
        tasks.append("classify")
    if params.ai_enrichment:
        tasks.append("enrich")
    return tasks


class TaxonomyDraftParams(_Params):
    """Borrador de manifiesto de taxonomía con IA a partir de una muestra de ``sample_size`` documentos convertidos.

    No escribe nada: el borrador va en el resultado del run y se guarda, si se quiere, con el ``PUT`` del manifiesto.
    """

    operation: Literal["taxonomy_draft"] = "taxonomy_draft"
    sample_size: int = Field(default=25, ge=1, le=60)


class ContextEvaluateParams(_Params):
    """Evaluar el contexto construido contra una referencia (W5, G3): el Excel subido o las decisiones del proyecto.

    No escribe nada: el informe (por eje: exactitud, cobertura, precisión, *recall*, confusiones y desglose por quién
    clasificó) va en el resultado del run.
    """

    operation: Literal["context_evaluate"] = "context_evaluate"
    gold: Literal["xlsx", "decisions"] = "xlsx"


class ContextDryRunParams(_Params):
    """Comparar cambios (W5, G3): clasificar los documentos de la referencia con otra configuración (plantilla o
    manifiesto, modelo de clasificar, alcance de la IA o perfil), **sin guardar nada**, y compararlo con el contexto
    actual. ``template_markdown`` lo fija la API al encolar (como en ``context_build``); con IA, ``max_documents`` es el
    presupuesto de documentos enviados."""

    operation: Literal["context_dry_run"] = "context_dry_run"
    gold: Literal["xlsx", "decisions"] = "xlsx"
    catalog: Literal["template", "manifest"] = "manifest"
    template_name: TemplateName | None = None
    ai_scope: Literal["off", "unclassified", "missing_axes"] = "off"
    model_classify: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/@-]{0,127}$")] | None = None
    profile_markdown: str | None = Field(default=None, max_length=32_768)
    max_documents: int = Field(default=50, ge=1, le=5000)
    template_markdown: str | None = Field(default=None, max_length=MAX_TEMPLATE_BYTES)

    @model_validator(mode="after")
    def _catalog_fields(self) -> ContextDryRunParams:
        if (self.catalog == "template") != (self.template_name is not None):
            raise ValueError("«template_name» se indica solo, y siempre, con el catálogo «template»")
        return self


class TaxonomyAgentParams(_Params):
    """Diseñar la taxonomía con IA (W7, ``TaxonomyDesignAgent``, tarea ``agent``): mejora el manifiesto del proyecto,
    una plantilla o, sin ninguno, diseña uno, probando cada cambio con las reglas contra todos los documentos.

    **No guarda nada**: la propuesta va en el resultado para revisarla. ``template_markdown`` (el de partida) lo fija la
    API al encolar. ``max_steps`` es el tope de llamadas al modelo.
    """

    operation: Literal["taxonomy_agent"] = "taxonomy_agent"
    catalog: Literal["manifest", "template", "none"] = "manifest"
    template_name: TemplateName | None = None
    instructions: str = Field(default="", max_length=2000)
    max_steps: int = Field(default=30, ge=1, le=60)
    template_markdown: str | None = Field(default=None, max_length=MAX_TEMPLATE_BYTES)

    @model_validator(mode="after")
    def _catalog_fields(self) -> TaxonomyAgentParams:
        if (self.catalog == "template") != (self.template_name is not None):
            raise ValueError("«template_name» se indica solo, y siempre, con el catálogo «template»")
        return self


class TaxonomyCheckParams(_Params):
    """Comprobar un manifiesto por reglas (W7, ``check_taxonomy_rules``) contra todos los documentos convertidos, sin
    IA y sin guardar nada: cobertura, conflictos, entradas vacías y palabras clave sin uso por eje."""

    operation: Literal["taxonomy_check"] = "taxonomy_check"
    markdown: str = Field(min_length=1, max_length=MAX_TEMPLATE_BYTES)


RunParams = Annotated[
    NoopParams
    | HistoryClearParams
    | ProjectMoveParams
    | ProjectDeleteParams
    | ScanParams
    | ExportZipParams
    | ExportXlsxParams
    | ExportSiteParams
    | ExportAiBundleParams
    | SearchIndexParams
    | DedupPreviewParams
    | DedupApplyParams
    | ContextBuildParams
    | ContextDeleteParams
    | TaxonomyDraftParams
    | ContextEvaluateParams
    | ContextDryRunParams
    | TaxonomyAgentParams
    | TaxonomyCheckParams,
    Field(discriminator="operation"),
]
RUN_PARAMS: Final[TypeAdapter[RunParams]] = TypeAdapter(RunParams)

#: Parámetros que deben coincidir entre la vista previa y la ejecución real.
_PREVIEW_KEYS: Final[dict[str, tuple[str, ...]]] = {
    "history_clear": (),
    "project_move": ("destination_location_id", "destination_parent", "new_folder"),
    "project_delete": ("delete_outputs",),
    # Exclusiones y patrones: si cambiaron desde la vista previa, su recuento de «excluidos» ya no vale.
    "scan": ("force", "exclusions", "ignore_patterns"),
    "dedup_apply": ("groups_run_id", "mode", "groups"),
    "context_delete": (),
}


@dataclass(frozen=True)
class OperationSpec:
    """Propiedades fijas de una operación.

    Attributes:
        min_role: Rol mínimo en el proyecto para lanzarla.
        queue: Cola por defecto (``scan`` con ``use_gpu`` va a ``gpu``, ver ``queue_for``).
        destructive: Mueve o borra ficheros: exige vista previa (``dry_run``) y confirmación.
        produces_artifacts: Deja ficheros en el workspace (cuenta para la cuota).
    """

    min_role: MemberRole
    queue: RunQueue = "cpu"
    destructive: bool = False
    produces_artifacts: bool = False


OPERATIONS: Final[dict[str, OperationSpec]] = {
    "noop": OperationSpec(min_role="editor", produces_artifacts=True),
    "history_clear": OperationSpec(min_role="owner", destructive=True),
    "project_move": OperationSpec(min_role="owner", destructive=True),
    "project_delete": OperationSpec(min_role="owner", destructive=True),
    "scan": OperationSpec(min_role="editor", produces_artifacts=True),
    # Exportar no cambia el proyecto: cualquier miembro, como en la web integrada (decisión del mantenedor, Fase 5).
    "export_zip": OperationSpec(min_role="viewer", produces_artifacts=True),
    "export_xlsx": OperationSpec(min_role="viewer", produces_artifacts=True),
    # Entrega del contexto (W8): como las exportaciones; el sitio se construye sobre una copia (no escribe en el destino).
    "export_site": OperationSpec(min_role="viewer", produces_artifacts=True),
    "export_ai_bundle": OperationSpec(min_role="viewer", produces_artifacts=True),
    "search_index": OperationSpec(min_role="editor"),
    # Duplicados (Fase 6): mover saca ficheros del origen, así que es de owner (ver min_role).
    "dedup_preview": OperationSpec(min_role="editor", produces_artifacts=True),
    "dedup_apply": OperationSpec(min_role="editor", destructive=True),
    # Contexto (Fase 7): construir reescribe solo lo que gestiona el contexto; borrarlo es de owner (regla 7).
    "context_build": OperationSpec(min_role="editor"),
    "context_delete": OperationSpec(min_role="owner", destructive=True),
    # IA (Fase 8): el borrador no escribe en el proyecto, pero envía su contenido fuera (decisión D4: editor).
    "taxonomy_draft": OperationSpec(min_role="editor"),
    # Calidad (W5): no escriben en el proyecto; la clasificación de prueba puede enviar contenido a la IA (editor).
    "context_evaluate": OperationSpec(min_role="editor"),
    "context_dry_run": OperationSpec(min_role="editor"),
    # Agentes (W7): no escriben en el proyecto; el diseñador envía contenido a la IA (editor, como el borrador).
    "taxonomy_agent": OperationSpec(min_role="editor"),
    "taxonomy_check": OperationSpec(min_role="editor"),
}


def is_write(params: RunParams) -> bool:
    """Si el run escribe en el proyecto (bloqueo de una escritura a la vez): las destructivas sin ``dry_run``, el
    escaneo (escribe las salidas), salvo su vista previa, y el reindexado de la búsqueda."""
    if isinstance(params, ScanParams):
        return not params.dry_run
    if isinstance(params, SearchIndexParams):  # un solo escritor de search.db (el escaneo también reindexa)
        return True
    if isinstance(params, DedupApplyParams):
        return not params.dry_run
    if isinstance(params, ContextBuildParams):
        return True
    return isinstance(params, _Destructive) and not params.dry_run


def needs_preview(params: RunParams) -> bool:
    """Si la ejecución real exige una vista previa confirmada (regla 7)."""
    if isinstance(params, ScanParams):
        return params.force and not params.dry_run
    if isinstance(params, DedupApplyParams):
        return not params.dry_run
    return OPERATIONS[params.operation].destructive and is_write(params)


def min_role(params: RunParams) -> MemberRole:
    """Rol mínimo para lanzar ``params``: «forzar reconversión» borra salidas, así que es de ``owner``."""
    if isinstance(params, ScanParams) and params.force:
        return "owner"
    if isinstance(params, DedupApplyParams) and params.mode == "move":
        return "owner"
    return OPERATIONS[params.operation].min_role


def queue_for(params: RunParams) -> RunQueue:
    """Cola del run: un escaneo con GPU necesita un worker de la cola ``gpu``."""
    if isinstance(params, ScanParams) and params.use_gpu and not params.dry_run:
        return "gpu"
    return OPERATIONS[params.operation].queue


def preview_matches(params: RunParams, preview: dict[str, object]) -> bool:
    """Si la vista previa ``preview`` (``params`` guardados) corresponde a la ejecución real ``params``."""
    if preview.get("operation") != params.operation or preview.get("dry_run") is not True:
        return False
    # Se compara lo guardado con lo guardado: listas de modelos (grupos de duplicados) como JSON.
    current = stored_params(params)
    return all(preview.get(key) == current.get(key) for key in _PREVIEW_KEYS.get(params.operation, ()))


def stored_params(params: RunParams) -> dict[str, object]:
    """Parámetros tal como se guardan en ``runs.params`` (sin secretos: ninguna operación los recibe)."""
    return params.model_dump(mode="json")


#: Parámetros guardados que no se devuelven en la API (``public_params``).
HIDDEN_PARAMS: Final[dict[str, tuple[str, ...]]] = {
    "context_build": ("template_markdown",),
    "context_dry_run": ("template_markdown", "profile_markdown"),
    "taxonomy_agent": ("template_markdown",),
    "taxonomy_check": ("markdown",),
}
