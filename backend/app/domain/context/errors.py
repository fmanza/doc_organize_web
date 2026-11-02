"""Errores de dominio del contexto y las plantillas de taxonomía (Fase 7), con ``code`` estable para el cliente."""

from __future__ import annotations

from app.core.errors import AppError


class TemplateNotFoundError(AppError):
    """No existe la plantilla de taxonomía."""

    status = 404
    title = "Plantilla no encontrada"
    code = "template_not_found"


class TemplateBuiltinError(AppError):
    """El nombre es de una plantilla incluida en doc_organize: no se puede crear, cambiar ni borrar (decisión C2)."""

    status = 409
    title = "Plantilla incluida"
    code = "template_builtin"


class TemplateInvalidError(AppError):
    """El nombre o el Markdown de la plantilla (o del manifiesto) no son válidos; ``detail`` explica por qué."""

    status = 422
    title = "Plantilla de taxonomía no válida"
    code = "template_invalid"


class ContextNotFoundError(AppError):
    """El proyecto no tiene contexto construido (o no existe ese dominio)."""

    status = 404
    title = "Contexto no encontrado"
    code = "context_not_found"


class InvalidContextBuildError(AppError):
    """Parámetros de construcción no válidos (carpeta reservada o distinta de la del contexto, falta el manifiesto…)."""

    status = 422
    title = "Construcción del contexto no válida"
    code = "context_build_invalid"


class DestinationReadOnlyError(AppError):
    """El contexto y el manifiesto se escriben en el destino: no se puede con una ubicación de solo lectura."""

    status = 422
    title = "La ubicación de destino es de solo lectura"
    code = "location_read_only"


class ManifestReplacedError(AppError):
    """``taxonomy_manifest.md`` no es un fichero normal (p. ej. un enlace simbólico): no se lee ni se sobrescribe."""

    status = 409
    title = "El manifiesto no es un fichero normal"
    code = "manifest_replaced"


class SiteNotFoundError(AppError):
    """Sitio no construido, token no válido o caducado, o fichero inexistente (mismo error en todos los casos)."""

    status = 404
    title = "No encontrado"
    code = "site_not_found"
