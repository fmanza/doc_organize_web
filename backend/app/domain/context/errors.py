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


class ManifestNotFoundError(AppError):
    """El proyecto no tiene ``taxonomy_manifest.md`` (al borrarlo)."""

    status = 404
    title = "El proyecto no tiene manifiesto"
    code = "manifest_not_found"


class ManifestVersionNotFoundError(AppError):
    """No existe esa versión del manifiesto en el proyecto (o es de otro proyecto: mismo error)."""

    status = 404
    title = "Versión del manifiesto no encontrada"
    code = "manifest_version_not_found"


class ManifestVersionInvalidError(AppError):
    """La versión no es un manifiesto válido: no se restaura (se puede cargar en el editor para arreglarla)."""

    status = 422
    title = "La versión del manifiesto no es válida"
    code = "manifest_version_invalid"


class ManifestChangedError(AppError):
    """El manifiesto cambió desde que se leyó (``If-Match`` no coincide): otro usuario, un job o una edición fuera."""

    status = 409
    title = "El manifiesto ha cambiado"
    code = "manifest_changed"


class ManifestEtagRequiredError(AppError):
    """Guardar, borrar o restaurar el manifiesto exige la cabecera ``If-Match`` con el ``etag`` leído."""

    status = 428
    title = "Falta If-Match"
    code = "etag_required"


class SiteNotFoundError(AppError):
    """Sitio no construido, token no válido o caducado, o fichero inexistente (mismo error en todos los casos)."""

    status = 404
    title = "No encontrado"
    code = "site_not_found"


class ProfileReplacedError(AppError):
    """``.doc_organize/profile.md`` (o su carpeta) no es un fichero (carpeta) normal: no se lee ni se sobrescribe."""

    status = 409
    title = "El perfil no es un fichero normal"
    code = "profile_replaced"


class ProfileChangedError(AppError):
    """El perfil del proyecto cambió desde que se leyó (``If-Match`` distinto)."""

    status = 409
    title = "El perfil ha cambiado"
    code = "profile_changed"


class ProfileEtagRequiredError(AppError):
    """Falta ``If-Match`` al cambiar el perfil del proyecto."""

    status = 428
    title = "Falta If-Match"
    code = "etag_required"


class ProfileTooLargeError(AppError):
    """El perfil del proyecto pasa del tamaño máximo."""

    status = 422
    title = "Perfil demasiado grande"
    code = "profile_invalid"


class PromptPreviewError(AppError):
    """No hay catálogo con el que componer la vista previa del prompt (sin manifiesto, o no es válido)."""

    status = 422
    title = "Vista previa del prompt no disponible"
    code = "prompt_preview_invalid"


class DecisionDocumentNotFoundError(AppError):
    """El documento de la decisión no está en el contexto construido."""

    status = 404
    title = "Documento no encontrado en el contexto"
    code = "decision_document_not_found"


class DecisionInvalidError(AppError):
    """La decisión no es válida (eje o valor fuera del catálogo, varios valores en un eje que no los admite…)."""

    status = 422
    title = "Decisión no válida"
    code = "decision_invalid"


class DecisionNotFoundError(AppError):
    """No hay ninguna decisión vigente con ese identificador."""

    status = 404
    title = "Decisión no encontrada"
    code = "decision_not_found"


class GoldInvalidError(AppError):
    """La referencia no sirve: no es un Excel, falta la hoja o la columna, o no tiene documentos etiquetados."""

    status = 422
    title = "Referencia no válida"
    code = "gold_invalid"


class GoldNotFoundError(AppError):
    """No hay referencia en Excel subida (o no hay decisiones con las que hacer una)."""

    status = 422
    title = "Sin referencia"
    code = "gold_not_found"


class RedactionRequiredError(AppError):
    """Solo un administrador de la instancia puede sacar el paquete para IA sin redactar credenciales (S-F7-1)."""

    status = 403
    title = "Redactar credenciales es obligatorio"
    code = "redaction_required"
