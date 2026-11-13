"""Servicios de IA de doc_organize 0.14.0 (WB-8.1…WB-8.3; L-3, G3). Único módulo que importa ``doc_organize.ai``.

La web construye los ``*Config`` con los valores que resuelve ella (``ai_settings`` > ``DOC_ORGANIZE_*``) y nunca usa
las ``*_config_from_store_or_env`` (obsoletas, se retiran en 1.0.0). doc_organize se importa **dentro** de cada función
(G15).

Firmas verificadas en el tag ``v0.14.0`` (CHANGELOG, «Firmas finales»), sin cambios en ``v1.0.0rc2``::

    LiteLLMClassificationConfig(base_url, virtual_key, model="claude-classifier", timeout_s=30.0, retries=0,
        retry_backoff_s=0.5)                                    # y Taxonomy…, …ManifestDraft… (timeout_s=60.0)
    LiteLLMUsageConfig(base_url, virtual_key, timeout_s=30.0, retries=0, retry_backoff_s=0.5)
    GitHubCopilotUsageConfig(username, personal_access_token, timeout_s=30.0, retries=0, retry_backoff_s=0.5)
    DomainClassificationClient(config, *, transport=None).classify(*, chunks_text, title, candidate_domains)
    TaxonomyClassificationClient(config, *, transport=None).classify(*, chunks_text, title, candidate_domains,
        candidate_material_types)
    TaxonomyManifestDraftClient(config, *, transport=None).propose_manifest(*, documents: list[SampledDocument])
    LiteLLMUsageClient(config, *, transport=None).get_usage(*, key=None)   # sin ?key= con la clave propia (L-3e)
    GitHubCopilotUsageClient(config, *, transport=None).get_usage(*, year=None, month=None) -> UsageSnapshot
    select_document_sample(documents, sample_size, *, roots=None) -> list[SampledDocument]          # L-3d
    render_taxonomy_manifest_markdown(manifest, *, reasoning, sample_document_count, total_document_count) -> str
    ContextBuilder().build(..., *, ai_max_failures=None, ai_max_documents=None) -> Context           # L-3a, L-3b
    Context.ai_classification_stopped / ai_documents_sent / ai_documents_classified / ai_documents_failed  # L-3c

Desde 0.14.0 la librería para la Sub-fase B ante una clave rechazada, tras ``MAX_CONNECTION_FAILURES`` errores de
conexión seguidos o al llegar al presupuesto, reintenta solo errores de transporte y cuenta lo que hace (G33–G35
resueltos). La muestra del borrador se toma relativa a la ubicación de origen (``roots``, G36) y el cliente de uso ya
no pone la clave en la URL (G37; ``core/logging.py`` sigue silenciando ``httpx`` como defensa).

Los mensajes de error de doc_organize llevan la ``base_url``. Aquí se sustituyen por un código fijo (``AiErrorCode``),
y en ningún caso llevan la clave.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, Final, Literal

from app.integrations.doc_organize.context import SourceFolder, converted_documents

if TYPE_CHECKING:
    import httpx

FamilyKey = Literal[
    "litellm_classification",
    "litellm_taxonomy_classification",
    "litellm_taxonomy_manifest_draft",
    "litellm_usage",
    "github_copilot_usage",
]
AiErrorCode = Literal["ai_auth", "ai_connection", "ai_error"]
UsageSourceKey = Literal["litellm", "github_copilot"]

logger = logging.getLogger(__name__)

#: Errores de conexión seguidos tras los que doc_organize deja de llamar al servicio en un run (``ai_max_failures``).
MAX_CONNECTION_FAILURES: Final = 3
#: Documentos de la muestra del borrador de manifiesto (mismos límites que la web integrada).
MAX_SAMPLE_SIZE: Final = 60


@dataclass(frozen=True)
class FieldSpec:
    """Campo de una familia: nombre, variable ``DOC_ORGANIZE_*`` equivalente, si es secreto y si es obligatorio."""

    name: str
    env_var: str
    secret: bool
    required: bool


@dataclass(frozen=True)
class FamilySpec:
    """Una de las 5 familias de configuración de IA (mismas claves y variables que la web integrada)."""

    key: FamilyKey
    fields: tuple[FieldSpec, ...]

    def field(self, name: str) -> FieldSpec | None:
        """El campo ``name``, o ``None``."""
        return next((f for f in self.fields if f.name == name), None)


def _litellm(key: FamilyKey, prefix: str, *, model: bool = True) -> FamilySpec:
    fields = [
        FieldSpec("base_url", f"{prefix}_BASE_URL", secret=False, required=True),
        FieldSpec("virtual_key", f"{prefix}_VIRTUAL_KEY", secret=True, required=True),
    ]
    if model:
        fields.append(FieldSpec("model", f"{prefix}_MODEL", secret=False, required=False))
    return FamilySpec(key, tuple(fields))


#: Orden fijo: primero las 3 de clasificación y borrador (todas de LiteLLM) y después las 2 de uso.
FAMILIES: Final[tuple[FamilySpec, ...]] = (
    _litellm("litellm_classification", "DOC_ORGANIZE_LITELLM_CLASSIFICATION"),
    _litellm("litellm_taxonomy_classification", "DOC_ORGANIZE_LITELLM_TAXONOMY_CLASSIFICATION"),
    _litellm("litellm_taxonomy_manifest_draft", "DOC_ORGANIZE_LITELLM_TAXONOMY_MANIFEST_DRAFT"),
    _litellm("litellm_usage", "DOC_ORGANIZE_LITELLM", model=False),
    FamilySpec(
        "github_copilot_usage",
        (
            FieldSpec("username", "DOC_ORGANIZE_GITHUB_USERNAME", secret=False, required=True),
            FieldSpec("pat", "DOC_ORGANIZE_GITHUB_PAT", secret=True, required=True),
        ),
    ),
)
FAMILIES_BY_KEY: Final[dict[str, FamilySpec]] = {family.key: family for family in FAMILIES}


@dataclass(frozen=True)
class AiConnection:
    """Valores ya resueltos de una familia para un uso concreto. ``values`` no sale en ``repr`` (lleva la clave).

    Attributes:
        values: Campo → valor (solo los que tienen valor).
        timeout_s: Segundos máximos de cada petición.
        retries: Reintentos de un timeout o error de transporte (``*Config.retries``, L-3b).
        budget: Documentos que se pueden enviar como mucho por construcción (``ai_max_documents``, L-3b).
    """

    family: FamilyKey
    values: dict[str, str] = field(repr=False)
    timeout_s: float = 30.0
    retries: int = 0
    budget: int = 500


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
    """Transporte HTTP de los clientes: el de httpx por defecto (``None``). Los tests lo sustituyen por un
    ``httpx.MockTransport``; los reintentos los hace doc_organize (``*Config.retries``)."""
    del connection
    return None


def _litellm_kwargs(connection: AiConnection) -> dict[str, Any]:
    values = connection.values
    kwargs: dict[str, Any] = {
        "base_url": values["base_url"],
        "virtual_key": values["virtual_key"],
        "timeout_s": connection.timeout_s,
        "retries": connection.retries,
    }
    if values.get("model"):
        kwargs["model"] = values["model"]
    return kwargs


# --- clasificación (subproceso del job, dentro del bucle de ``ContextBuilder.build``) ---------------------------------


def config_for(connection: AiConnection) -> Any:
    """``*Config`` de doc_organize de la familia de ``connection``."""
    from doc_organize.core.models import (
        GitHubCopilotUsageConfig,
        LiteLLMClassificationConfig,
        LiteLLMTaxonomyClassificationConfig,
        LiteLLMTaxonomyManifestDraftConfig,
        LiteLLMUsageConfig,
    )

    if connection.family == "github_copilot_usage":
        return GitHubCopilotUsageConfig(
            username=connection.values["username"],
            personal_access_token=connection.values["pat"],
            timeout_s=connection.timeout_s,
            retries=connection.retries,
        )
    if connection.family == "litellm_usage":
        kwargs = _litellm_kwargs(connection)
        kwargs.pop("model", None)
        return LiteLLMUsageConfig(**kwargs)
    config_cls = {
        "litellm_classification": LiteLLMClassificationConfig,
        "litellm_taxonomy_classification": LiteLLMTaxonomyClassificationConfig,
        "litellm_taxonomy_manifest_draft": LiteLLMTaxonomyManifestDraftConfig,
    }[connection.family]
    return config_cls(**_litellm_kwargs(connection))


def classification_client(connection: AiConnection) -> Any:
    """Cliente de la familia de ``connection`` (un eje o taxonomía), para ``ContextBuilder.build``.

    Se usa con ``async with`` dentro del mismo bucle de eventos que la construcción. El presupuesto y los cortes van
    en ``classification_limits``.
    """
    from doc_organize.ai import DomainClassificationClient, TaxonomyClassificationClient

    clients = {
        "litellm_classification": DomainClassificationClient,
        "litellm_taxonomy_classification": TaxonomyClassificationClient,
    }
    if connection.family not in clients:
        raise ValueError(f"{connection.family} no es una familia de clasificación")
    return clients[connection.family](config_for(connection), transport=_transport(connection))


def classification_limits(connection: AiConnection) -> dict[str, int]:
    """Argumentos de ``ContextBuilder.build`` que acotan la Sub-fase B (L-3a, L-3b)."""
    return {"ai_max_failures": MAX_CONNECTION_FAILURES, "ai_max_documents": connection.budget}


def classification_stats(context: Any) -> dict[str, Any]:
    """Lo que hizo la IA en una construcción, desde el ``Context`` de doc_organize (L-3c)."""
    return {
        "calls": int(context.ai_documents_sent),
        "classified": int(context.ai_documents_classified),
        "failed": int(context.ai_documents_failed),
        "stopped": context.ai_classification_stopped,
    }


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


def location_root(folder: SourceFolder) -> Path:
    """Raíz de la ubicación de origen de ``folder`` (``folder.root`` sin los niveles de ``folder.folder``).

    La muestra del borrador muestra las carpetas relativas a ella (``2024/obras``), nunca por encima (G36).
    """
    levels = len(PurePosixPath(folder.folder).parts)
    return folder.root.parents[levels - 1] if levels else folder.root


def _ai_error(exc: Exception, auth: type[Exception], connection: type[Exception]) -> AiServiceError:
    if isinstance(exc, auth):
        return AiServiceError("ai_auth")
    if isinstance(exc, connection):
        return AiServiceError("ai_connection")
    return AiServiceError("ai_error")


def draft_manifest(
    connection: AiConnection, folders: list[SourceFolder], sample_size: int, *, name: str, created_at: datetime
) -> DraftOutcome:
    """Pide a la IA un borrador de manifiesto con una muestra de los documentos convertidos. No guarda nada.

    Raises:
        NoConvertedDocumentsError: No hay documentos convertidos legibles.
        AiServiceError: Falló la llamada (código sin detalle).
    """
    from doc_organize.ai import TaxonomyManifestDraftClient
    from doc_organize.context.taxonomy_manifest import render_taxonomy_manifest_markdown
    from doc_organize.context.taxonomy_manifest_sampler import select_document_sample
    from doc_organize.core.exceptions import (
        TaxonomyManifestDraftAuthError,
        TaxonomyManifestDraftConnectionError,
        TaxonomyManifestDraftError,
    )
    from doc_organize.core.models import TaxonomyManifest

    del name, created_at  # el borrador no depende del proyecto de doc_organize, solo de sus documentos
    documents, _ = converted_documents(folders)
    if not documents:
        raise NoConvertedDocumentsError()
    roots = sorted({str(location_root(folder)) for folder in folders})
    sample = asyncio.run(select_document_sample(documents, min(sample_size, MAX_SAMPLE_SIZE), roots=roots))
    if not sample:
        raise NoConvertedDocumentsError()

    async def _propose() -> Any:
        async with TaxonomyManifestDraftClient(config_for(connection), transport=_transport(connection)) as client:
            return await client.propose_manifest(documents=sample)

    try:
        result = asyncio.run(_propose())
    except TaxonomyManifestDraftError as exc:
        import httpx

        error = _ai_error(exc, TaxonomyManifestDraftAuthError, TaxonomyManifestDraftConnectionError)
        cause = exc.__cause__  # doc_organize encadena el error de httpx (``raise ... from exc``)
        error.timed_out = error.code == "ai_connection" and isinstance(cause, httpx.TimeoutException)
        # Solo nombres de clase: el mensaje de doc_organize lleva la base_url y nunca se registra la clave.
        logger.warning(
            "Falló el borrador de manifiesto con IA",
            extra={
                "family": connection.family,
                "error": error.code,
                "timed_out": error.timed_out,
                "exc_type": type(exc).__name__,
                "cause": type(cause).__name__ if cause is not None else None,
                "timeout_s": connection.timeout_s,
                "retries": connection.retries,
            },
        )
        raise error from None
    manifest = TaxonomyManifest(domains=result.domains, material_types=result.material_types)
    markdown = render_taxonomy_manifest_markdown(
        manifest, reasoning=result.reasoning, sample_document_count=len(sample), total_document_count=len(documents)
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


async def fetch_usage(source: UsageSourceKey, connection: AiConnection) -> UsageReport:
    """Uso del periodo actual de ``source`` (LiteLLM: la propia clave; Copilot: el mes en curso).

    Raises:
        AiServiceError: Falló la consulta (código sin detalle).
    """
    from doc_organize.ai import GitHubCopilotUsageClient, LiteLLMUsageClient
    from doc_organize.core.exceptions import UsageSourceAuthError, UsageSourceConnectionError, UsageSourceError

    try:
        if source == "litellm":
            async with LiteLLMUsageClient(config_for(connection), transport=_transport(connection)) as client:
                snapshot = await client.get_usage()
        else:
            today = date.today()
            async with GitHubCopilotUsageClient(config_for(connection), transport=_transport(connection)) as client:
                snapshot = await client.get_usage(year=today.year, month=today.month)
    except UsageSourceError as exc:
        raise _ai_error(exc, UsageSourceAuthError, UsageSourceConnectionError) from None
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
