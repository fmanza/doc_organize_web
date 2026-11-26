"""Contexto, taxonomías, manifiesto y perfil (Fase 7)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.api.v1.schemas._common import _Out


class CatalogEntryOut(BaseModel):
    """Dominio o tipo de material de una plantilla o manifiesto."""

    slug: str
    name: str


class TaxonomyTemplateOut(BaseModel):
    """Plantilla de taxonomía en el listado: ``builtin`` = incluida en doc_organize (solo lectura)."""

    name: str
    title: str | None
    description: str | None
    builtin: bool
    updated_at: datetime | None = None


class TaxonomyTemplateList(BaseModel):
    items: list[TaxonomyTemplateOut]


class TaxonomyAxisSummaryOut(BaseModel):
    """Un eje de una plantilla o manifiesto (doc_organize 2.0): clave, nombre, si organiza carpetas y nº de valores."""

    key: str
    name: str
    organizes: Literal["folder", "subfolder"] | None
    multiple: bool
    values: int


class FrontMatterReportOut(BaseModel):
    """Lo que doc_organize leerá del front matter (``inspect_taxonomy_front_matter``), para avisar al guardar.

    ``implicit_axes``: ejes leídos del formato implícito de 1.x (conviene declararlos en ``axes:``).
    ``ignored_keys``: claves de nivel superior que no se usan al clasificar. ``legacy_format``: el texto es de 1.x.
    """

    axes: list[TaxonomyAxisSummaryOut] = []
    implicit_axes: list[str] = []
    ignored_keys: list[str] = []
    legacy_format: bool = False


class TaxonomyTemplateDetail(TaxonomyTemplateOut):
    """Plantilla con su Markdown, su catálogo y lo que avisa su front matter (W3)."""

    markdown: str
    domains: list[CatalogEntryOut]
    material_types: list[CatalogEntryOut]
    front_matter: FrontMatterReportOut = FrontMatterReportOut()


class TaxonomyMarkdownIn(BaseModel):
    """Markdown de una plantilla o manifiesto: front matter YAML (``domains``, ``material_types``) y prosa."""

    model_config = ConfigDict(extra="forbid")

    markdown: str = Field(min_length=1, max_length=262_144)


class TaxonomyManifestOut(BaseModel):
    """``taxonomy_manifest.md`` del proyecto: ``markdown`` nulo si no existe; ``error`` si no es válido.

    ``etag`` se envía en ``If-Match`` al guardar, borrar o restaurar (``"none"`` si no hay manifiesto).
    ``last_changed_at`` es la fecha de la versión más reciente (último cambio hecho desde la app), o nula.
    """

    markdown: str | None
    error: str | None = None
    domains: list[CatalogEntryOut] = []
    material_types: list[CatalogEntryOut] = []
    front_matter: FrontMatterReportOut = FrontMatterReportOut()
    etag: str
    last_changed_at: datetime | None = None


class ProfileSectionsOut(BaseModel):
    """Secciones de un perfil de proyecto (doc_organize 2.0, G2): lo que se envía al modelo al clasificar."""

    context: str | None = None
    tie_breakers: str | None = None
    glossary: str | None = None
    examples: list[str] = []


class ProjectProfileOut(BaseModel):
    """``.doc_organize/profile.md`` del proyecto (D11: se añade al perfil de la plantilla o el manifiesto).

    ``markdown`` nulo si no existe; ``sections`` lo que doc_organize reconoce (nulo si ninguna sección). ``etag`` se
    envía en ``If-Match`` al guardar o borrar (``"none"`` si no hay perfil).
    """

    markdown: str | None
    sections: ProfileSectionsOut | None = None
    etag: str


class ProjectProfileIn(BaseModel):
    """Perfil propio del proyecto: Markdown con las secciones ``## Contexto del proyecto``, ``## Reglas de
    desempate``, ``## Glosario`` y ``## Ejemplos``."""

    model_config = ConfigDict(extra="forbid")

    markdown: str = Field(min_length=1, max_length=32_768)


class PromptPreviewIn(BaseModel):
    """Vista previa del prompt de clasificación: con la plantilla ``template_name`` o con el manifiesto del proyecto, y
    con ``profile_markdown`` (un borrador sin guardar) o, si es nulo, el perfil guardado."""

    model_config = ConfigDict(extra="forbid")

    catalog: Literal["template", "manifest"] = "manifest"
    template_name: str | None = Field(default=None, max_length=64)
    profile_markdown: str | None = Field(default=None, max_length=32_768)


class TemplatePromptPreviewIn(BaseModel):
    """Vista previa del prompt de una plantilla (su perfil, sin el de ningún proyecto)."""

    model_config = ConfigDict(extra="forbid")

    markdown: str = Field(min_length=1, max_length=262_144)


class PromptMessageOut(BaseModel):
    role: str
    content: str


class PromptPreviewOut(BaseModel):
    """Lo que recibiría el modelo al clasificar (sin llamarlo): los mensajes y el perfil de la plantilla, el del
    proyecto y el compuesto que va en el prompt."""

    messages: list[PromptMessageOut]
    template_profile: ProfileSectionsOut | None = None
    project_profile: ProfileSectionsOut | None = None
    profile: ProfileSectionsOut | None = None


class ManifestVersionOut(BaseModel):
    """Versión anterior del manifiesto (sin el texto): lo que había antes de ``action``.

    ``empty``: no había manifiesto. ``valid``: era un manifiesto válido (se puede restaurar).
    """

    id: int
    created_at: datetime
    created_by: str | None
    action: Literal["save", "delete", "restore", "history_clear"]
    empty: bool
    valid: bool
    domains: int | None
    material_types: int | None


class ManifestVersionList(BaseModel):
    items: list[ManifestVersionOut]
    #: Cuántas se conservan por proyecto.
    limit: int


class ManifestVersionDetail(ManifestVersionOut):
    markdown: str | None


class ContextDomainOut(BaseModel):
    slug: str
    name: str
    description: str | None
    status: str
    documents: int


class ContextAxisValueOut(BaseModel):
    """Un valor de un eje del contexto y cuántos documentos lo tienen."""

    slug: str
    name: str
    documents: int


class ContextAxisOut(BaseModel):
    """Un eje del contexto (``Context.taxonomy_axes``, doc_organize 2.0) con sus valores y recuentos."""

    key: str
    name: str
    description: str | None = None
    multiple: bool = False
    organizes: Literal["folder", "subfolder"] | None = None
    values: list[ContextAxisValueOut]


class PromptProvenanceOut(BaseModel):
    """Con qué prompt y qué modelo se hizo una tarea de IA en la construcción (``Context.ai_provenance``)."""

    task: str
    prompt_id: str
    version: str
    source: str = Field(description="builtin (empaquetado) o project (prompt propio del proyecto)")
    model: str


class FreshnessExamplesOut(BaseModel):
    changed: list[str] = []
    added: list[str] = []
    removed: list[str] = []
    unknown: list[str] = []


class ContextFreshnessOut(BaseModel):
    """Si el contexto sigue al día respecto a la caché del último escaneo (W4, ``check_context_freshness``).

    Recuentos de originales cambiados, nuevos, que ya no están y sin huella (``unknown``: contextos anteriores a 2.0,
    no se sabe si cambiaron; no cuentan para ``up_to_date``), si el sitio quedó desfasado y unos pocos ejemplos con
    rutas relativas. Se calcula al escanear y al construir, sin leer originales.
    """

    checked_at: datetime
    up_to_date: bool
    changed: int
    added: int
    removed: int
    unknown: int
    stale_site: bool
    examples: FreshnessExamplesOut = FreshnessExamplesOut()


class VersionGroupOut(BaseModel):
    """Versiones de un mismo documento (``Context.version_groups``, F5): miembros de la versión más baja a la más
    alta, con rutas relativas, la vigente y si una persona la confirmó."""

    key: str
    members: list[str]
    versions: list[str]
    current: str
    confirmed: bool = False


class ContextOut(BaseModel):
    """Resumen del contexto construido del proyecto (proyección del último ``context_build``)."""

    output_folder_name: str
    catalog_kind: str
    taxonomy_template_name: str | None
    documents_count: int
    unclassified_count: int
    failed_count: int
    collisions_count: int
    site_built: bool
    ai_classification: bool = False
    #: Trazabilidad (1.5.0): versión de doc_organize y modelos de IA usados; nulos en contextos anteriores.
    built_with_version: str | None = None
    ai_classification_model: str | None = None
    ai_enrichment_model: str | None = None
    domains: list[ContextDomainOut]
    #: W3 (doc_organize 2.0): ejes con recuentos por valor y procedencia de la IA; vacíos en contextos anteriores.
    taxonomy_axes: list[ContextAxisOut] = []
    ai_provenance: list[PromptProvenanceOut] = []
    #: W4: frescura respecto a la caché del último escaneo; nula si aún no se ha comprobado.
    freshness: ContextFreshnessOut | None = None
    #: W6 (F5): modo de versiones de la construcción, sus grupos y las versiones antiguas fuera del contexto.
    versions_mode: Literal["all", "mark", "current_only"] | None = None
    #: 2.5.0: si la construcción agrupó versiones entre formatos; nulo en las anteriores.
    versions_across_extensions: bool | None = None
    version_groups: list[VersionGroupOut] = []
    superseded: list[str] = []
    superseded_count: int = 0
    built_by_run_id: str | None
    built_at: datetime


class AxisValueOut(_Out):
    """Un valor de un eje de un documento: quién lo asignó (``rules``, ``semantic``, ``ai`` o ``human``) y, si lo dio
    la IA, la cita literal y si se encontró en el texto enviado (D10: sin verificar, confianza bajo el umbral)."""

    slug: str
    name: str
    confidence: float | None = None
    classified_by: Literal["rules", "semantic", "ai", "human"] | None = None
    evidence: str | None = None
    evidence_verified: bool | None = None


class ContextDocumentOut(_Out):
    """Documento del contexto: original (``folder`` + ``path``) y copia relativa a la carpeta del proyecto."""

    title: str
    domain_slug: str | None
    document_type: str | None
    material_type: str | None
    material_type_name: str | None
    folder: str
    path: str
    organized_path: str | None
    failed: bool
    collision: bool
    classified_by: Literal["rules", "semantic", "ai", "human"] | None = None
    output_path: str | None = None
    # 1.5.0: propiedades declaradas en el documento (o de la IA si faltan: ``ai_filled``) e idioma detectado.
    author: str | None = None
    description: str | None = None
    keywords: list[str] = []
    language: str | None = None
    ai_filled: list[str] = []
    # 1.5.0: cómo se clasificó. Reglas y su confianza, propuesta de la IA (puede diferir del dominio) y justificación.
    rules_domain: str | None = None
    rules_confidence: float | None = None
    ai_domain: str | None = None
    ai_confidence: float | None = None
    ai_reasoning: str | None = None
    material_type_confidence: float | None = None
    # 1.6.0 (G42): por qué no se clasificó; los sin clasificar traen también sus propiedades y lo que propusieron las
    # reglas por debajo del umbral (``rules_domain``, ``rules_confidence``). Nulo en contextos anteriores.
    unclassified_reason: Literal["incomplete_artifacts", "below_threshold"] | None = None
    #: W3 (doc_organize 2.0): valores de cada eje, por clave de eje; vacío en contextos anteriores a 2.0.
    axes: dict[str, list[AxisValueOut]] = {}
    #: W6 (F5): versión del documento en su grupo, la clave del grupo y si es la vigente (nulos sin grupo).
    version: str | None = None
    version_group: str | None = None
    is_current: bool | None = None


class ContextChangeOut(BaseModel):
    """Documento que entró, salió o cambió de dominio o tipo de material en una construcción (1.5.0)."""

    path: str = Field(description="Original relativo a la carpeta de origen (``<carpeta>/<ruta>``)")
    #: doc_organize 2.0: ``superseded`` (versión antigua fuera del contexto) y ``excluded`` (lo sacó una persona).
    change: Literal["added", "removed", "reclassified", "superseded", "excluded"]
    previous_domain: str | None
    domain: str | None
    previous_material_type: str | None
    material_type: str | None
    classified_by: str | None


class ContextBuildOut(BaseModel):
    """Una construcción del historial del contexto (1.5.0)."""

    built_at: str
    previous_built_at: str | None
    built_with_version: str | None
    taxonomy_manifest_used: bool
    ai_classification_model: str | None
    ai_enrichment_model: str | None
    classified: int
    unclassified: int
    changes_total: int = Field(description="Cambios de la construcción; en ``changes`` van como mucho los primeros")
    changes: list[ContextChangeOut]


class ContextHistoryOut(BaseModel):
    """Últimas construcciones del contexto, las más recientes primero (1.5.0). Se conserva al borrar el contexto."""

    items: list[ContextBuildOut]
    total: int
    error: Literal["history_too_large"] | None = Field(
        default=None, description="No se leyó: el historial es demasiado grande; usa la exportación a Excel"
    )


class ContextDocumentPage(BaseModel):
    items: list[ContextDocumentOut]
    total: int


class SiteSessionOut(BaseModel):
    """URL del sitio aislado (con su token) y su caducidad."""

    url: str
    expires_at: datetime
