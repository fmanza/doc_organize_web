"""Servicios de IA de doc_organize 2.0 (W2; antes WB-8.1…WB-8.3, L-3, G3). Único módulo que importa ``doc_organize.ai``.

doc_organize 2.0 sustituye los cuatro clientes de 1.x (clasificación, clasificación por taxonomía, borrador de
manifiesto y descripciones) por un **cliente único** (``LlmClient``) con un modelo, y si se quiere una clave, **por
tarea** (``AiSettings``/``TaskSettings``). La web guarda su configuración en la familia ``litellm`` (``ai_settings``,
migración ``0016``) y construye aquí el ``AiSettings``; nunca usa ``settings_from_env`` de la librería, pero sí su lista
de variables de 1.x (``legacy_variables``) para avisar de las que ya no se leen (D15, U17). doc_organize se importa
**dentro** de cada función (G15).

Firmas verificadas en el tag ``v2.0.0rc2``::

    AiSettings(base_url, virtual_key, tasks: dict[AiTask, TaskSettings] = {}, timeout_s=120.0, retries=0,
        retry_backoff_s=0.5, rate_limit_retries=3, max_retry_wait_s=60.0, redact_credentials=True, tags=[])
    TaskSettings(model, virtual_key=None, max_tokens=None)        # sin tarea: alias «doc-organize-<tarea>»
    LlmClient(settings, *, transport=None)                       # async with; complete_json, complete_with_tools, embed
    draft_taxonomy(llm, prompts, documents) -> LlmResult[TaxonomyManifestDraftResult]
    select_document_sample(documents, sample_size, *, roots=None) -> list[SampledDocument]
    render_taxonomy_manifest_markdown(manifest, *, reasoning, sample_document_count, total_document_count) -> str
    ContextBuilder().build(project, documents, *, llm=None, ai_scope="off", enrich=False, ...,
        ai_max_failures=None, ai_max_documents=None) -> Context
    Context.ai_stats.classification / .enrichment: AiPhaseStats(sent, assigned, failed, stopped, cached, ...)
    LiteLLMUsageClient / GitHubCopilotUsageClient             # sin cambios desde 1.x
    AiError > AiAuthError, AiConnectionError, AiResponseError  # doc_organize.core.exceptions

Los mensajes de error de doc_organize llevan la ``base_url``. Aquí se sustituyen por un código fijo (``AiErrorCode``),
y en ningún caso llevan la clave.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Literal

from app.integrations.doc_organize.context import SourceFolder, converted_documents, location_root

if TYPE_CHECKING:
    import httpx

FamilyKey = Literal["litellm", "litellm_usage", "github_copilot_usage"]
#: Tareas de IA de doc_organize 2.0 (``AI_TASKS``): clasificar, describir, diseñar la taxonomía, agentes y embeddings.
TaskKey = Literal["classify", "enrich", "taxonomy_design", "agent", "embed"]
TASKS: Final[tuple[TaskKey, ...]] = ("classify", "enrich", "taxonomy_design", "agent", "embed")
#: Tareas con presupuesto de documentos por construcción (``ai_max_documents``): las que recorren el corpus.
BUDGET_TASKS: Final[tuple[TaskKey, ...]] = ("classify", "enrich")
AiErrorCode = Literal["ai_auth", "ai_connection", "ai_error"]
#: Resultado de «Probar conexión»: los de ``AiErrorCode`` y ``ai_model`` (el modelo no respondió: alias inexistente o no
#: permitido para la clave).
TestErrorCode = Literal["ai_auth", "ai_connection", "ai_error", "ai_model"]
ModelAccess = Literal["ok", "denied", "unknown"]
#: Familias que llaman a un modelo (las que admiten «Probar el modelo»).
MODEL_FAMILIES: Final[frozenset[str]] = frozenset({"litellm"})
UsageSourceKey = Literal["litellm", "github_copilot"]

logger = logging.getLogger(__name__)

#: Errores de conexión seguidos tras los que doc_organize deja de llamar al servicio en un run (``ai_max_failures``).
MAX_CONNECTION_FAILURES: Final = 3
#: Documentos de la muestra del borrador de manifiesto (mismos límites que la web integrada).
MAX_SAMPLE_SIZE: Final = 60
#: Variables de entorno de la familia ``litellm`` (las de doc_organize 2.0, ``settings_from_env``).
ENV_PREFIX: Final = "DOC_ORGANIZE_LITELLM_"


@dataclass(frozen=True)
class FieldSpec:
    """Campo de una familia: nombre, variable ``DOC_ORGANIZE_*`` equivalente (``None`` si no tiene), si es secreto, si
    es obligatorio y, en la familia ``litellm``, de qué tarea es (``None`` = de todas)."""

    name: str
    env_var: str | None
    secret: bool
    required: bool
    task: TaskKey | None = None


@dataclass(frozen=True)
class FamilySpec:
    """Una de las 3 familias de configuración de IA."""

    key: FamilyKey
    fields: tuple[FieldSpec, ...]

    def field(self, name: str) -> FieldSpec | None:
        """El campo ``name``, o ``None``."""
        return next((f for f in self.fields if f.name == name), None)


def _litellm_fields() -> tuple[FieldSpec, ...]:
    """URL y clave general (obligatorias) y, por tarea, modelo, clave propia (D12) y presupuesto (opcionales)."""
    fields = [
        FieldSpec("base_url", f"{ENV_PREFIX}BASE_URL", secret=False, required=True),
        FieldSpec("virtual_key", f"{ENV_PREFIX}VIRTUAL_KEY", secret=True, required=True),
    ]
    for task in TASKS:
        upper = task.upper()
        fields.append(FieldSpec(f"model_{task}", f"{ENV_PREFIX}MODEL_{upper}", secret=False, required=False, task=task))
        fields.append(
            FieldSpec(f"virtual_key_{task}", f"{ENV_PREFIX}VIRTUAL_KEY_{upper}", secret=True, required=False, task=task)
        )
        if task in BUDGET_TASKS:
            fields.append(FieldSpec(f"budget_{task}", None, secret=False, required=False, task=task))
    return tuple(fields)


#: Orden fijo: la de los modelos (todas las tareas) y después las 2 de uso.
FAMILIES: Final[tuple[FamilySpec, ...]] = (
    FamilySpec("litellm", _litellm_fields()),
    FamilySpec(
        "litellm_usage",
        (
            FieldSpec("base_url", f"{ENV_PREFIX}BASE_URL", secret=False, required=True),
            FieldSpec("virtual_key", f"{ENV_PREFIX}VIRTUAL_KEY", secret=True, required=True),
        ),
    ),
    FamilySpec(
        "github_copilot_usage",
        (
            FieldSpec("username", "DOC_ORGANIZE_GITHUB_USERNAME", secret=False, required=True),
            FieldSpec("pat", "DOC_ORGANIZE_GITHUB_PAT", secret=True, required=True),
        ),
    ),
)
FAMILIES_BY_KEY: Final[dict[str, FamilySpec]] = {family.key: family for family in FAMILIES}


#: Tareas largas (una sola petición o una conversación con herramientas): usan el plazo y los reintentos «largos».
LONG_TASKS: Final[tuple[TaskKey, ...]] = ("taxonomy_design", "agent")


def default_model(task: TaskKey) -> str:
    """Alias recomendado de ``task`` en el proxy cuando no se configura su modelo (``default_model_alias``, U10)."""
    from doc_organize.core.models import default_model_alias

    return str(default_model_alias(task))


def legacy_env(environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """Variables de entorno de 1.x definidas (``DOC_ORGANIZE_LITELLM_<CLIENTE>_*``) con la de 2.0 que las sustituye.

    doc_organize 2.0 y la web ya no las leen (D15): si siguen definidas, la configuración se queda sin ellas y hay que
    avisar (U17). Sin valores: solo nombres.
    """
    from doc_organize.ai import legacy_variables

    return dict(legacy_variables(environ))


@dataclass(frozen=True)
class AiConnection:
    """Valores ya resueltos de una familia para un uso concreto. ``values`` no sale en ``repr`` (lleva la clave).

    Attributes:
        values: Campo → valor (solo los que tienen valor).
        timeout_s: Segundos máximos de cada petición.
        retries: Reintentos de un timeout o error de transporte (``AiSettings.retries``, L-3b).
        long_timeout_s, long_retries: Los de las tareas largas (``LONG_TASKS``: borrador y agentes), como
            ``TaskSettings.timeout_s``/``retries`` de doc_organize 2.0.0rc1.
        budget: Documentos que se pueden enviar como mucho por construcción si la tarea no tiene presupuesto propio
            (``ai_max_documents``, L-3b).
        redact_credentials: Redactar credenciales de todo lo que sale hacia la IA (D7; por defecto, sí).
    """

    family: FamilyKey
    values: dict[str, str] = field(repr=False)
    timeout_s: float = 30.0
    retries: int = 0
    long_timeout_s: float = 300.0
    long_retries: int = 0
    budget: int = 500
    redact_credentials: bool = True

    def model_for(self, task: TaskKey) -> str:
        """Modelo de ``task``: el configurado o el alias recomendado."""
        return self.values.get(f"model_{task}") or default_model(task)

    def budget_for(self, task: TaskKey) -> int:
        """Presupuesto de documentos de ``task`` por construcción: el suyo o, si no tiene, el general."""
        raw = self.values.get(f"budget_{task}")
        return int(raw) if raw else self.budget


class AiServiceError(Exception):
    """Falló una llamada al servicio de IA; ``code`` dice de qué tipo (el mensaje no lleva ni URL ni clave).

    ``timed_out`` distingue, dentro de ``ai_connection``, que el servicio aceptó la conexión pero no respondió a
    tiempo (solo lo marca el borrador de manifiesto; ``AiErrorCode`` no cambia, así que el panel de uso tampoco).
    """

    def __init__(self, code: AiErrorCode, *, timed_out: bool = False) -> None:
        super().__init__(code)
        self.code: AiErrorCode = code
        self.timed_out = timed_out


class NoConvertedDocumentsError(Exception):
    """El proyecto no tiene documentos convertidos legibles para la muestra del borrador."""


def _transport(connection: AiConnection) -> httpx.AsyncBaseTransport | None:
    """Transporte HTTP de los clientes: el de httpx por defecto (``None``). Los tests lo sustituyen por un LiteLLM falso
    (``tests/fake_litellm.py``); los reintentos los hace doc_organize (``AiSettings.retries``)."""
    del connection
    return None


# --- cliente único (subproceso del job, dentro del bucle de ``ContextBuilder.build``) ---------------------------------


def ai_settings_for(connection: AiConnection) -> Any:
    """``AiSettings`` de doc_organize con la URL, la clave general y, por tarea, el modelo, la clave, el presupuesto de
    documentos (``TaskSettings.max_documents``) y, en las tareas largas, su plazo y sus reintentos (2.0.0rc1).

    Una tarea sin nada propio no entra en ``tasks``: usa el alias recomendado, la clave general y los plazos generales.
    """
    from doc_organize.core.models import AiSettings, TaskSettings

    if connection.family != "litellm":
        raise ValueError(f"{connection.family} no es la familia de los modelos")
    values = connection.values
    tasks: dict[str, Any] = {}
    for task in TASKS:
        model = values.get(f"model_{task}")
        key = values.get(f"virtual_key_{task}")
        budget = values.get(f"budget_{task}")
        long = task in LONG_TASKS
        if model or key or budget or long:
            tasks[task] = TaskSettings(
                model=model or default_model(task),
                virtual_key=key or None,
                max_documents=int(budget) if budget else None,
                timeout_s=connection.long_timeout_s if long else None,
                retries=connection.long_retries if long else None,
            )
    return AiSettings(
        base_url=values["base_url"],
        virtual_key=values["virtual_key"],
        tasks=tasks,
        timeout_s=connection.timeout_s,
        retries=connection.retries,
        redact_credentials=connection.redact_credentials,
        tags=["doc_organize_web"],
    )


def llm_client(connection: AiConnection) -> Any:
    """``LlmClient`` de ``connection`` para ``ContextBuilder.build(llm=...)``. Se usa con ``async with`` dentro del mismo
    bucle de eventos que la construcción; el presupuesto y los cortes van en ``build_limits``."""
    from doc_organize.ai import LlmClient

    return LlmClient(ai_settings_for(connection), transport=_transport(connection))


def build_limits(connection: AiConnection, tasks: list[TaskKey]) -> dict[str, int]:
    """Argumentos de ``ContextBuilder.build`` que acotan las fases de IA (L-3a, L-3b).

    ``ai_max_documents`` es el general (``ai_max_documents_per_run``); el propio de cada tarea va en
    ``TaskSettings.max_documents`` (``ai_settings_for``) y doc_organize 2.0.0rc1 aplica el menor a cada fase, así que
    clasificar y describir pueden tener presupuestos distintos.
    """
    del tasks
    return {"ai_max_failures": MAX_CONNECTION_FAILURES, "ai_max_documents": connection.budget}


def phase_stats(phase: Any) -> dict[str, Any]:
    """Recuento de una fase de IA (``AiPhaseStats``) con los nombres que ya usaba el resultado del run.

    ``calls`` son los documentos enviados al modelo; ``cached`` (2.0) los resueltos con la caché de resultados de IA,
    sin llamar; ``classified``/``applied`` los que recibieron algo de la IA.
    """
    return {
        "calls": int(phase.sent),
        "failed": int(phase.failed),
        "stopped": phase.stopped,
        "cached": int(phase.cached),
        "prompt_tokens": int(phase.prompt_tokens),
        "completion_tokens": int(phase.completion_tokens),
        "response_format": phase.response_format,
    }


def classification_stats(context: Any) -> dict[str, Any]:
    """Lo que hizo la clasificación con IA en una construcción (``Context.ai_stats.classification``)."""
    phase = context.ai_stats.classification
    return {**phase_stats(phase), "classified": int(phase.assigned), "scope": str(context.ai_stats.scope)}


def enrichment_stats(context: Any) -> dict[str, Any]:
    """Lo que hizo el enriquecimiento con IA en una construcción (``Context.ai_stats.enrichment``)."""
    phase = context.ai_stats.enrichment
    return {**phase_stats(phase), "applied": int(phase.assigned)}


# --- borrador de manifiesto (subproceso del job) ---------------------------------------------------------------------


@dataclass(frozen=True)
class DraftOutcome:
    """Borrador de manifiesto propuesto por la IA: Markdown listo para el editor y su resumen."""

    markdown: str
    reasoning: str | None
    sample_documents: int
    total_documents: int
    domains: list[tuple[str, str]]
    material_types: list[tuple[str, str]]


def _ai_error(exc: Exception) -> AiServiceError:
    from doc_organize.core.exceptions import AiAuthError, AiConnectionError

    if isinstance(exc, AiAuthError):
        return AiServiceError("ai_auth")
    if isinstance(exc, AiConnectionError):
        return AiServiceError("ai_connection")
    return AiServiceError("ai_error")


def draft_manifest(
    connection: AiConnection,
    folders: list[SourceFolder],
    sample_size: int,
    *,
    name: str,
    created_at: datetime,
    project_root: Path | None = None,
) -> DraftOutcome:
    """Pide a la IA (tarea ``taxonomy_design``) un borrador de manifiesto con una muestra de los documentos convertidos.
    No guarda nada.

    Args:
        project_root: Carpeta del proyecto, para los prompts propios (``<raíz>/.doc_organize/prompts/``); ``None`` =
            los empaquetados.

    Raises:
        NoConvertedDocumentsError: No hay documentos convertidos legibles.
        AiServiceError: Falló la llamada (código sin detalle).
    """
    from doc_organize.ai import LlmClient, PromptRegistry, draft_taxonomy
    from doc_organize.context.taxonomy_manifest import render_taxonomy_manifest_markdown
    from doc_organize.context.taxonomy_manifest_sampler import select_document_sample
    from doc_organize.core.exceptions import AiError

    del name, created_at  # el borrador no depende del proyecto de doc_organize, solo de sus documentos
    documents, _ = converted_documents(folders)
    if not documents:
        raise NoConvertedDocumentsError()
    roots = sorted({str(location_root(folder)) for folder in folders})
    sample = asyncio.run(select_document_sample(documents, min(sample_size, MAX_SAMPLE_SIZE), roots=roots))
    if not sample:
        raise NoConvertedDocumentsError()

    async def _propose() -> Any:
        async with LlmClient(ai_settings_for(connection), transport=_transport(connection)) as llm:
            prompts = PromptRegistry(str(project_root)) if project_root is not None else PromptRegistry()
            return (await draft_taxonomy(llm, prompts, sample)).value

    try:
        result = asyncio.run(_propose())
    except AiError as exc:
        import httpx

        error = _ai_error(exc)
        cause = exc.__cause__  # doc_organize encadena el error de httpx (``raise ... from exc``)
        error.timed_out = error.code == "ai_connection" and isinstance(cause, httpx.TimeoutException)
        # Solo nombres de clase: el mensaje de doc_organize lleva la base_url y nunca se registra la clave.
        logger.warning(
            "Falló el borrador de manifiesto con IA",
            extra={
                "family": connection.family,
                "task": "taxonomy_design",
                "error": error.code,
                "timed_out": error.timed_out,
                "exc_type": type(exc).__name__,
                "cause": type(cause).__name__ if cause is not None else None,
                "timeout_s": connection.long_timeout_s,
                "retries": connection.long_retries,
            },
        )
        raise error from None
    markdown = render_taxonomy_manifest_markdown(
        result.to_manifest(),
        reasoning=result.reasoning,
        sample_document_count=len(sample),
        total_document_count=len(documents),
    )
    return DraftOutcome(
        markdown=str(markdown),
        reasoning=result.reasoning,
        sample_documents=len(sample),
        total_documents=len(documents),
        domains=[(entry.slug, entry.name) for entry in result.domains],
        material_types=[(entry.slug, entry.name) for entry in result.material_types],
    )


# --- uso (API, con caché corta en ``domain/ai/usage.py``) ------------------------------------------------------------


@dataclass(frozen=True)
class UsageItem:
    date: str
    product: str
    sku: str | None
    quantity: float
    unit_type: str
    cost_usd: float | None


@dataclass(frozen=True)
class UsageReport:
    """``UsageSnapshot`` sin ``raw`` (el payload original de la fuente nunca sale de aquí)."""

    period_start: str
    period_end: str
    items: list[UsageItem]


def _usage_config(connection: AiConnection) -> Any:
    """``LiteLLMUsageConfig`` (con la clave general) o ``GitHubCopilotUsageConfig`` de ``connection``."""
    from doc_organize.core.models import GitHubCopilotUsageConfig, LiteLLMUsageConfig

    values = connection.values
    if connection.family == "github_copilot_usage":
        return GitHubCopilotUsageConfig(
            username=values["username"],
            personal_access_token=values["pat"],
            timeout_s=connection.timeout_s,
            retries=connection.retries,
        )
    return LiteLLMUsageConfig(
        base_url=values["base_url"],
        virtual_key=values["virtual_key"],
        timeout_s=connection.timeout_s,
        retries=connection.retries,
    )


async def fetch_usage(source: UsageSourceKey, connection: AiConnection) -> UsageReport:
    """Uso del periodo actual de ``source`` (LiteLLM: la propia clave; Copilot: el mes en curso).

    Raises:
        AiServiceError: Falló la consulta (código sin detalle).
    """
    from doc_organize.ai import GitHubCopilotUsageClient, LiteLLMUsageClient
    from doc_organize.core.exceptions import UsageSourceAuthError, UsageSourceConnectionError, UsageSourceError

    try:
        if source == "litellm":
            async with LiteLLMUsageClient(_usage_config(connection), transport=_transport(connection)) as client:
                snapshot = await client.get_usage()
        else:
            today = date.today()
            async with GitHubCopilotUsageClient(_usage_config(connection), transport=_transport(connection)) as client:
                snapshot = await client.get_usage(year=today.year, month=today.month)
    except UsageSourceError as exc:
        raise _usage_error(exc, UsageSourceAuthError, UsageSourceConnectionError) from None
    except (ValueError, TypeError, AttributeError):  # respuesta que no es el JSON esperado (o no cumple el modelo)
        raise AiServiceError("ai_error") from None
    return UsageReport(
        period_start=str(snapshot.period_start),
        period_end=str(snapshot.period_end),
        items=[
            UsageItem(
                date=str(item.date),
                product=str(item.product),
                sku=item.sku,
                quantity=float(item.quantity),
                unit_type=str(item.unit_type),
                cost_usd=None if item.cost_usd is None else float(item.cost_usd),
            )
            for item in snapshot.items
        ],
    )


def _usage_error(exc: Exception, auth: type[Exception], connection: type[Exception]) -> AiServiceError:
    if isinstance(exc, auth):
        return AiServiceError("ai_auth")
    if isinstance(exc, connection):
        return AiServiceError("ai_connection")
    return AiServiceError("ai_error")


# --- probar la conexión (API, «Probar conexión» de Configuración IA) ---------------------------------------------------


@dataclass(frozen=True)
class ConnectionCheck:
    """Resultado de una prueba: sin URL, clave ni cuerpo de la respuesta, solo un código.

    Attributes:
        error: ``None`` si fue bien.
        model_access: Si la clave de LiteLLM tiene acceso al modelo según ``/key/info`` (``unknown`` si no lo dice o la
            familia no tiene modelo).
        model_checked: Si se envió una petición al modelo.
        elapsed_ms: Duración de la prueba.
        task: Tarea cuyo modelo se probó (familia ``litellm``), o ``None``.
        response_format: Con qué formato respondió el modelo (``json_schema`` si admite la salida estricta, o
            ``json_object``); ``None`` si no se probó o no aplica (embeddings).
    """

    error: TestErrorCode | None
    model_access: ModelAccess
    model_checked: bool
    elapsed_ms: int
    task: TaskKey | None = None
    response_format: str | None = None


#: Texto de la petición mínima al modelo: no es un documento real y no pide nada que se guarde.
_PROBE_TEXT: Final = "Prueba de conexión de doc_organize_web. Responde ok=true."
_PROBE_SCHEMA: Final[dict[str, Any]] = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"}},
    "required": ["ok"],
    "additionalProperties": False,
}


def _model_access(raw: dict[str, Any], model: str | None) -> ModelAccess:
    """Lo que dice ``/key/info`` de ``model``: ``models`` vacío (o ausente) es «todos»; con lista, tiene que estar."""
    info = raw.get("info", raw) if isinstance(raw, dict) else {}
    models = info.get("models") if isinstance(info, dict) else None
    if not model or not isinstance(models, list):
        return "unknown"
    if not models or "all-proxy-models" in models:
        return "ok"
    return "ok" if model in models else "denied"


async def _check_key(connection: AiConnection, task: TaskKey | None) -> tuple[TestErrorCode | None, ModelAccess]:
    """``GET /key/info`` (LiteLLM, con la clave general) o el uso del mes (GitHub Copilot): servidor alcanzable y
    credencial válida."""
    from doc_organize.ai import GitHubCopilotUsageClient, LiteLLMUsageClient
    from doc_organize.core.exceptions import UsageSourceAuthError, UsageSourceConnectionError, UsageSourceError

    try:
        if connection.family == "github_copilot_usage":
            today = date.today()
            async with GitHubCopilotUsageClient(_usage_config(connection), transport=_transport(connection)) as client:
                await client.get_usage(year=today.year, month=today.month)
            return None, "unknown"
        model = connection.model_for(task) if connection.family in MODEL_FAMILIES and task else None
        async with LiteLLMUsageClient(_usage_config(connection), transport=_transport(connection)) as client:
            snapshot = await client.get_usage()
    except UsageSourceError as exc:
        return _usage_error(exc, UsageSourceAuthError, UsageSourceConnectionError).code, "unknown"
    except (ValueError, TypeError, AttributeError):  # respuesta que no es el JSON esperado
        return "ai_error", "unknown"
    return None, _model_access(snapshot.raw, model)


async def _check_model(connection: AiConnection, task: TaskKey) -> tuple[TestErrorCode | None, str | None]:
    """Una petición mínima a ``task`` con su modelo y su clave (gasta unos pocos tokens): JSON con esquema estricto o,
    en ``embed``, un embedding. Devuelve el error y el formato con que respondió."""
    from doc_organize.ai import LlmClient
    from doc_organize.core.exceptions import AiError

    try:
        async with LlmClient(ai_settings_for(connection), transport=_transport(connection)) as llm:
            if task == "embed":
                await llm.embed([_PROBE_TEXT])
                return None, None
            result = await llm.complete_json(
                task,
                [{"role": "user", "content": _PROBE_TEXT}],
                schema=_PROBE_SCHEMA,
                parse=lambda data: bool(data["ok"]),
                schema_name="probe",
            )
    except AiError as exc:
        code = _ai_error(exc).code
        # El resto (HTTP 400/404 de un alias que no existe, o una respuesta que no es JSON) es cosa del modelo.
        return ("ai_model" if code == "ai_error" else code), None
    return None, str(result.response_format)


def check_connection(
    connection: AiConnection, *, model_check: bool = False, task: TaskKey = "classify"
) -> ConnectionCheck:
    """Prueba ``connection`` sin guardar nada: primero la credencial y, si se pide y la familia tiene modelo, el modelo
    de ``task``.

    No lanza excepciones del servicio: el resultado lleva el código del error. Nunca registra la URL ni la clave.
    """
    if model_check and connection.family not in MODEL_FAMILIES:
        raise ValueError(f"{connection.family} no llama a un modelo")
    started = time.monotonic()
    tested_task: TaskKey | None = task if connection.family in MODEL_FAMILIES else None

    async def _run() -> tuple[TestErrorCode | None, ModelAccess, bool, str | None]:
        error, access = await _check_key(connection, tested_task)
        if error is not None and not (model_check and error == "ai_auth"):
            return error, access, False, None
        if not model_check:
            return error, access, False, None
        # Un 401/403 en ``/key/info`` puede ser política del proxy: la prueba del modelo es la que decide.
        model_error, response_format = await _check_model(connection, task)
        return model_error, access, True, response_format

    error, access, checked, response_format = asyncio.run(_run())
    elapsed = int((time.monotonic() - started) * 1000)
    logger.info(
        "Prueba de conexión de IA",
        extra={"family": connection.family, "task": tested_task, "error": error, "model_checked": checked},
    )
    return ConnectionCheck(
        error=error,
        model_access=access,
        model_checked=checked,
        elapsed_ms=elapsed,
        task=tested_task,
        response_format=response_format,
    )
