"""Servicios de IA de doc_organize 0.13.0 (WB-8.1…WB-8.3; L-3, G3). Único módulo que importa ``doc_organize.ai``.

La web construye los ``*Config`` con los valores que resuelve ella (``ai_settings`` > ``DOC_ORGANIZE_*``) y nunca usa
las ``*_config_from_store_or_env`` (obsoletas, se retiran en 1.0.0). doc_organize se importa **dentro** de cada función
(G15).

Firmas verificadas en el tag ``v0.13.0``::

    LiteLLMClassificationConfig(base_url, virtual_key, model="claude-classifier", timeout_s=30.0)    # y Taxonomy…
    LiteLLMTaxonomyManifestDraftConfig(base_url, virtual_key, model="claude-classifier", timeout_s=60.0)
    LiteLLMUsageConfig(base_url, virtual_key, timeout_s=30.0)
    GitHubCopilotUsageConfig(username, personal_access_token, timeout_s=30.0)
    DomainClassificationClient(config, *, transport=None).classify(*, chunks_text, title, candidate_domains)
    TaxonomyClassificationClient(config, *, transport=None).classify(*, chunks_text, title, candidate_domains,
        candidate_material_types)
    TaxonomyManifestDraftClient(config, *, transport=None).propose_manifest(*, documents: list[SampledDocument])
    LiteLLMUsageClient(config, *, transport=None).get_usage(*, key=None) -> UsageSnapshot
    GitHubCopilotUsageClient(config, *, transport=None).get_usage(*, year=None, month=None) -> UsageSnapshot
    select_document_sample(documents, sample_size) -> list[SampledDocument]
    render_taxonomy_manifest_markdown(manifest, *, reasoning, sample_document_count, total_document_count) -> str

Huecos que se rodean aquí (``docs/plan/DOC_ORGANIZE_GAPS.md``):

- G33: ``ContextBuilder`` captura el error de IA de cada documento y sigue con el siguiente. Los clientes «vigilados»
  dejan de llamar tras un error de autenticación o tras ``MAX_CONNECTION_FAILURES`` errores de conexión seguidos.
- G34: sin reintentos ni presupuesto. Se reintenta la conexión con ``httpx.AsyncHTTPTransport(retries=…)`` y el
  cliente deja de llamar al llegar a ``AiConnection.budget`` documentos.
- G35: la librería no cuenta lo que hace la IA. Lo cuenta ``AiTally``.
- G36: la muestra del borrador usa la carpeta de ``source_path``. Se le pasa la ruta relativa a la ubicación de origen
  para que no salgan al servicio de IA nombres de las carpetas del contenedor.

Los mensajes de error de doc_organize llevan la ``base_url``. Aquí se sustituyen por un código fijo (``AiErrorCode``),
y en ningún caso llevan la clave.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
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
StopReason = Literal["auth", "connection", "budget"]
UsageSourceKey = Literal["litellm", "github_copilot"]

#: Errores de conexión seguidos tras los que se deja de llamar al servicio en un run (G33).
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
        retries: Reintentos de conexión (``httpx.AsyncHTTPTransport``).
        budget: Documentos que se pueden enviar como mucho (clasificación).
    """

    family: FamilyKey
    values: dict[str, str] = field(repr=False)
    timeout_s: float = 30.0
    retries: int = 0
    budget: int = 500


@dataclass
class AiTally:
    """Lo que hizo la IA en un run (G35): llamadas, documentos con algún eje asignado, fallos y por qué paró."""

    calls: int = 0
    classified: int = 0
    failed: int = 0
    stopped: StopReason | None = None
    consecutive_connection_failures: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {"calls": self.calls, "classified": self.classified, "failed": self.failed, "stopped": self.stopped}


class AiServiceError(Exception):
    """Falló una llamada al servicio de IA; ``code`` dice de qué tipo (el mensaje no lleva ni URL ni clave)."""

    def __init__(self, code: AiErrorCode) -> None:
        super().__init__(code)
        self.code: AiErrorCode = code


class NoConvertedDocumentsError(Exception):
    """El proyecto no tiene documentos convertidos legibles para la muestra del borrador."""


def _transport(connection: AiConnection) -> httpx.AsyncBaseTransport:
    import httpx

    return httpx.AsyncHTTPTransport(retries=connection.retries)


def _litellm_kwargs(connection: AiConnection) -> dict[str, Any]:
    values = connection.values
    kwargs: dict[str, Any] = {
        "base_url": values["base_url"],
        "virtual_key": values["virtual_key"],
        "timeout_s": connection.timeout_s,
    }
    if values.get("model"):
        kwargs["model"] = values["model"]
    return kwargs


# --- clasificación (subproceso del job, dentro del bucle de ``ContextBuilder.build``) ---------------------------------


def _guard(
    base: type[Any], empty: Callable[[], Any], errors: tuple[type[Exception], type[Exception], type[Exception]]
) -> type[Any]:
    """Subclase de ``base`` que cuenta, respeta el presupuesto y deja de llamar tras un fallo de autenticación o
    varios de conexión (G33, G34). Devuelve el resultado vacío («sin dominio») cuando no llama.

    ``errors``: ``(Error, AuthError, ConnectionError)`` del cliente. Se relanzan con un mensaje fijo (sin ``base_url``):
    ``ContextBuilder`` los captura, escribe el aviso y sigue sin clasificar ese documento.
    """
    generic_error, auth_error, connection_error = errors

    class Guarded(base):  # type: ignore[misc]  # base es una clase de doc_organize (sin tipos)
        def __init__(self, connection: AiConnection, tally: AiTally) -> None:
            super().__init__(config_for(connection), transport=_transport(connection))
            self._budget = connection.budget
            self._tally = tally

        async def classify(self, **kwargs: Any) -> Any:
            tally = self._tally
            if tally.stopped is None and tally.calls >= self._budget:
                tally.stopped = "budget"
            if tally.stopped is not None:
                return empty()
            tally.calls += 1
            try:
                result = await super().classify(**kwargs)
            except auth_error:
                tally.failed += 1
                tally.stopped = "auth"
                raise auth_error("El servicio de IA rechazó la clave") from None
            except connection_error:
                tally.failed += 1
                tally.consecutive_connection_failures += 1
                if tally.consecutive_connection_failures >= MAX_CONNECTION_FAILURES:
                    tally.stopped = "connection"
                raise connection_error("No se pudo conectar con el servicio de IA") from None
            except generic_error:
                tally.failed += 1
                tally.consecutive_connection_failures = 0
                raise generic_error("El servicio de IA devolvió un error") from None
            tally.consecutive_connection_failures = 0
            if getattr(result, "domain", None) is not None or getattr(result, "material_type", None) is not None:
                tally.classified += 1
            return result

    return Guarded


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


def classification_client(connection: AiConnection, tally: AiTally) -> Any:
    """Cliente vigilado de la familia de ``connection`` (un eje o taxonomía), para ``ContextBuilder.build``.

    Se usa con ``async with`` dentro del mismo bucle de eventos que la construcción.
    """
    from doc_organize.ai import DomainClassificationClient, TaxonomyClassificationClient
    from doc_organize.core.exceptions import (
        DomainClassificationAuthError,
        DomainClassificationConnectionError,
        DomainClassificationError,
        TaxonomyClassificationAuthError,
        TaxonomyClassificationConnectionError,
        TaxonomyClassificationError,
    )
    from doc_organize.core.models import DomainClassificationResult, TaxonomyClassificationResult

    if connection.family == "litellm_taxonomy_classification":
        cls = _guard(
            TaxonomyClassificationClient,
            TaxonomyClassificationResult,
            (TaxonomyClassificationError, TaxonomyClassificationAuthError, TaxonomyClassificationConnectionError),
        )
    elif connection.family == "litellm_classification":
        cls = _guard(
            DomainClassificationClient,
            lambda: DomainClassificationResult(domain=None, confidence=0.0),
            (DomainClassificationError, DomainClassificationAuthError, DomainClassificationConnectionError),
        )
    else:
        raise ValueError(f"{connection.family} no es una familia de clasificación")
    return cls(connection, tally)


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


def _relative_documents(documents: list[Any], folders: list[SourceFolder]) -> list[Any]:
    """Copias de ``documents`` con ``source_path`` relativo a la ubicación de origen (G36)."""
    relative: list[Any] = []
    for document in documents:
        source = Path(document.source_path)
        for folder in folders:
            if source.is_relative_to(folder.root):
                rel = PurePosixPath(folder.folder, source.relative_to(folder.root).as_posix())
                relative.append(document.model_copy(update={"source_path": rel.as_posix()}))
                break
    return relative


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
    documents = _relative_documents(documents, folders)
    if not documents:
        raise NoConvertedDocumentsError()
    sample = asyncio.run(select_document_sample(documents, min(sample_size, MAX_SAMPLE_SIZE)))
    if not sample:
        raise NoConvertedDocumentsError()

    async def _propose() -> Any:
        async with TaxonomyManifestDraftClient(config_for(connection), transport=_transport(connection)) as client:
            return await client.propose_manifest(documents=sample)

    try:
        result = asyncio.run(_propose())
    except TaxonomyManifestDraftError as exc:
        raise _ai_error(exc, TaxonomyManifestDraftAuthError, TaxonomyManifestDraftConnectionError) from None
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
