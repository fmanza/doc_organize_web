"""Perfil del proyecto y vista previa del prompt (W3; doc_organize 2.0, G2 y D11).

El perfil propio del proyecto vive en el destino, en ``<proyecto>/.doc_organize/profile.md`` (donde lo lee
doc_organize al construir), con las secciones ``## Contexto del proyecto``, ``## Reglas de desempate``, ``## Glosario``
y ``## Ejemplos``; se **añade** al perfil del cuerpo de la plantilla o del manifiesto (D11). La plantilla lleva el suyo
en su cuerpo y se edita en el editor de plantillas (``templates.manage``).

- Leerlo y la vista previa: cualquier miembro. Guardarlo o borrarlo: propietario o editor, con el destino ``rw`` y sin
  escrituras en curso; con ``If-Match`` (``etag`` de lo leído) y auditado sin el texto.
- Se escribe sin seguir enlaces: si la carpeta ``.doc_organize`` o el fichero no son normales, no se toca
  (``profile_replaced``). La escritura es atómica (fichero temporal y ``os.replace``).
- La vista previa (``render_prompt_preview``) no llama al modelo: compone el catálogo y el perfil como los vería él.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Project, User
from app.domain.context import manifest_versions, templates
from app.domain.context.errors import (
    ProfileChangedError,
    ProfileEtagRequiredError,
    ProfileReplacedError,
    ProfileTooLargeError,
    PromptPreviewError,
    TemplateInvalidError,
)
from app.domain.context.service import _check_writable, _output_root, read_manifest
from app.domain.documents.errors import OutputNotFoundError, OutputTooLargeError
from app.domain.documents.service import read_inside
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction, RequestContext
from app.domain.locations.errors import LocationUnavailableError
from app.domain.locations.paths import run_with_timeout
from app.integrations.doc_organize import context as library

#: Tamaño máximo de ``profile.md`` (doc_organize envía como mucho 8000 caracteres de perfil compuesto).
MAX_PROFILE_BYTES: Final = 32 * 1024
NO_PROFILE_ETAG: Final = "none"


@dataclass(frozen=True)
class Profile:
    """``profile.md`` del proyecto: ``markdown`` nulo si no existe; ``sections`` lo que se reconoce de él."""

    markdown: str | None
    etag: str
    sections: library.ProfileSections | None = None


def _etag(markdown: str | None) -> str:
    if markdown is None:
        return NO_PROFILE_ETAG
    return hashlib.sha256(manifest_versions.normalize(markdown).encode("utf-8")).hexdigest()


def _regular(path: Path, kind: Literal["file", "dir"]) -> bool:
    """Si ``path`` existe como fichero (o carpeta) normal; ``False`` si no existe.

    Raises:
        ProfileReplacedError: Existe, pero no es de ese tipo (un enlace, por ejemplo).
    """
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return False
    if not (stat.S_ISREG(info.st_mode) if kind == "file" else stat.S_ISDIR(info.st_mode)):
        raise ProfileReplacedError()
    return True


def _read(path: Path, root: Path) -> str | None:
    if not _regular(path.parent, "dir") or not _regular(path, "file"):
        return None
    try:
        return read_inside(path, root, max_bytes=MAX_PROFILE_BYTES).decode("utf-8", errors="replace")
    except OutputNotFoundError:
        return None


def read_profile(settings: Settings, project: Project) -> Profile:
    """El perfil propio del proyecto (``markdown`` nulo si no tiene).

    Raises:
        ProfileReplacedError: ``profile.md`` o su carpeta no son normales.
        ContextNotFoundError, LocationUnavailableError: Ver ``_output_root``.
    """
    root = _output_root(settings, project)
    path = library.profile_file(root)
    try:
        markdown = run_with_timeout(lambda: _read(path, root), settings.location_probe_timeout_seconds)
    except OutputTooLargeError:
        raise ProfileTooLargeError(f"El perfil pasa de {MAX_PROFILE_BYTES // 1024} KiB.") from None
    if markdown is None:
        return Profile(markdown=None, etag=NO_PROFILE_ETAG)
    return Profile(markdown=markdown, etag=_etag(markdown), sections=library.parse_profile_text(markdown))


def _write(path: Path, markdown: str | None) -> None:
    """Escribe (o borra con ``None``) ``profile.md`` sin seguir enlaces; escritura atómica."""
    folder = path.parent
    if markdown is None:
        if _regular(folder, "dir") and _regular(path, "file"):
            os.unlink(path)
        return
    if not _regular(folder, "dir"):
        folder.mkdir()
    _regular(path, "file")
    descriptor, temporary = tempfile.mkstemp(dir=folder, prefix=".profile-", suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(manifest_versions.normalize(markdown))
        os.replace(temporary, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(temporary)
        raise


def _mutate(
    db: Session,
    settings: Settings,
    project: Project,
    markdown: str | None,
    *,
    if_match: str | None,
    actor: User,
    ctx: RequestContext,
) -> Profile:
    if not if_match:
        raise ProfileEtagRequiredError("Recarga el perfil y vuelve a intentarlo.")
    if markdown is not None and len(markdown.encode("utf-8")) > MAX_PROFILE_BYTES:
        raise ProfileTooLargeError(f"El perfil pasa de {MAX_PROFILE_BYTES // 1024} KiB.")
    _check_writable(db, project)
    root = _output_root(settings, project)
    path = library.profile_file(root)
    with manifest_versions.project_lock(project.id):
        current = read_profile(settings, project)
        if current.etag != if_match.strip('"'):
            raise ProfileChangedError("Otro usuario lo ha cambiado: recarga para ver su versión.")
        if _etag(markdown) != current.etag:
            try:
                run_with_timeout(lambda: _write(path, markdown), settings.location_probe_timeout_seconds)
            except (ProfileReplacedError, LocationUnavailableError):
                raise
            except OSError:
                raise LocationUnavailableError("No se pudo escribir el perfil en el destino.") from None
            saved = read_profile(settings, project)
            audit.record(
                db,
                action=AuditAction.PROJECT_PROFILE_DELETE if markdown is None else AuditAction.PROJECT_PROFILE_SAVE,
                ctx=ctx,
                actor_id=actor.id,
                target_type="project",
                target_id=project.id,
                # Sin el texto: solo qué secciones tiene (puede llevar contexto sensible del cliente).
                details={"sections": _section_names(saved.sections)},
            )
            db.commit()
            return saved
    return current


def _section_names(sections: library.ProfileSections | None) -> list[str]:
    if sections is None:
        return []
    names = [name for name in ("context", "tie_breakers", "glossary") if getattr(sections, name)]
    return [*names, "examples"] if sections.examples else names


def save_profile(
    db: Session,
    settings: Settings,
    project: Project,
    markdown: str,
    *,
    if_match: str | None,
    actor: User,
    ctx: RequestContext,
) -> Profile:
    """Guarda ``profile.md`` (el mismo texto no escribe ni audita).

    Raises:
        ProfileEtagRequiredError, ProfileChangedError, ProfileTooLargeError, ProfileReplacedError,
        DestinationReadOnlyError, WriteLockedError, LocationUnavailableError.
    """
    return _mutate(db, settings, project, markdown, if_match=if_match, actor=actor, ctx=ctx)


def delete_profile(
    db: Session, settings: Settings, project: Project, *, if_match: str | None, actor: User, ctx: RequestContext
) -> Profile:
    """Borra ``profile.md`` (sin él, nada que hacer)."""
    return _mutate(db, settings, project, None, if_match=if_match, actor=actor, ctx=ctx)


def preview(
    db: Session,
    settings: Settings,
    project: Project,
    actor: User,
    *,
    catalog: Literal["template", "manifest"],
    template_name: str | None,
    profile_markdown: str | None,
) -> library.PromptPreview:
    """Vista previa del prompt de clasificación del proyecto con la plantilla ``template_name`` o el manifiesto, y el
    perfil ``profile_markdown`` (un borrador sin guardar) o, sin él, el guardado. No llama al modelo.

    Raises:
        PromptPreviewError: Sin manifiesto o no válido, o sin plantilla.
        TemplateNotFoundError: No existe la plantilla.
    """
    if catalog == "template":
        if not template_name:
            raise PromptPreviewError("Elige una plantilla.")
        markdown = templates.template_markdown(db, actor, template_name)
    else:
        manifest = read_manifest(settings, project)
        if manifest.markdown is None or manifest.error:
            raise PromptPreviewError(manifest.error or "El proyecto no tiene manifiesto de taxonomía.")
        markdown = manifest.markdown
    if profile_markdown is None:
        profile_markdown = read_profile(settings, project).markdown
    elif len(profile_markdown.encode("utf-8")) > MAX_PROFILE_BYTES:
        raise ProfileTooLargeError(f"El perfil pasa de {MAX_PROFILE_BYTES // 1024} KiB.")
    root = _output_root(settings, project)
    try:
        return run_with_timeout(
            lambda: library.prompt_preview(markdown, project_profile=profile_markdown, project_root=root),
            settings.location_probe_timeout_seconds,
        )
    except library.TemplateInvalidError as exc:
        raise PromptPreviewError(str(exc)) from None


def template_preview(markdown: str) -> library.PromptPreview:
    """Vista previa del prompt de una plantilla (su perfil, sin el de ningún proyecto). No llama al modelo.

    Raises:
        TemplateInvalidError: El Markdown no es una plantilla válida.
    """
    templates.validate_markdown(markdown)
    try:
        return library.prompt_preview(markdown)
    except library.TemplateInvalidError as exc:
        raise TemplateInvalidError(str(exc)) from None
