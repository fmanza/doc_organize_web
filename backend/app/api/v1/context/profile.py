"""Perfil del proyecto y vista previa del prompt de clasificación (W3)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.api.deps import Context, CurrentUser, DbSession, SettingsDep, TemplateManager
from app.api.v1.context._shared import ERRORS, IfMatch
from app.api.v1.schemas import (
    ProfileSectionsOut,
    ProjectProfileIn,
    ProjectProfileOut,
    PromptMessageOut,
    PromptPreviewIn,
    PromptPreviewOut,
    TemplatePromptPreviewIn,
)
from app.domain.context import profile as profiles
from app.domain.projects import service as projects

router = APIRouter(tags=["context"])


def _sections_out(sections: Any) -> ProfileSectionsOut | None:
    if sections is None:
        return None
    return ProfileSectionsOut(
        context=sections.context,
        tie_breakers=sections.tie_breakers,
        glossary=sections.glossary,
        examples=list(sections.examples),
    )


def _profile_out(profile: profiles.Profile) -> ProjectProfileOut:
    return ProjectProfileOut(markdown=profile.markdown, sections=_sections_out(profile.sections), etag=profile.etag)


def _preview_out(preview: Any) -> PromptPreviewOut:
    return PromptPreviewOut(
        messages=[PromptMessageOut(role=role, content=content) for role, content in preview.messages],
        template_profile=_sections_out(preview.template_profile),
        project_profile=_sections_out(preview.project_profile),
        profile=_sections_out(preview.profile),
    )


_PROFILE_WRITE_ERRORS: dict[int | str, dict[str, Any]] = {
    **ERRORS,
    403: {"description": "Rol insuficiente (editor)"},
    409: {
        "description": "Cambió desde que se leyó (profile_changed), escritura en curso (write_locked) o no es un "
        "fichero normal (profile_replaced)"
    },
    422: {"description": "Demasiado grande (profile_invalid) o destino de solo lectura"},
    428: {"description": "Falta If-Match (etag_required)"},
    503: {"description": "Ubicación no disponible"},
}


@router.get(
    "/projects/{project_id}/context/profile",
    response_model=ProjectProfileOut,
    summary="Perfil del proyecto",
    responses=ERRORS,
)
def get_profile(project_id: int, user: CurrentUser, db: DbSession, settings: SettingsDep) -> ProjectProfileOut:
    """``.doc_organize/profile.md`` del proyecto y las secciones que reconoce doc_organize."""
    access = projects.get_access(db, project_id, user)
    return _profile_out(profiles.read_profile(settings, access.project))


@router.put(
    "/projects/{project_id}/context/profile",
    response_model=ProjectProfileOut,
    summary="Guardar el perfil del proyecto",
    responses=_PROFILE_WRITE_ERRORS,
)
def put_profile(
    project_id: int,
    body: ProjectProfileIn,
    user: CurrentUser,
    db: DbSession,
    settings: SettingsDep,
    ctx: Context,
    if_match: IfMatch = None,
) -> ProjectProfileOut:
    """Escribe el perfil propio del proyecto (D11: se añade al de la plantilla o el manifiesto). Propietario o editor,
    con el destino ``rw``; auditado sin el texto."""
    access = projects.get_access(db, project_id, user, min_role="editor")
    saved = profiles.save_profile(db, settings, access.project, body.markdown, if_match=if_match, actor=user, ctx=ctx)
    return _profile_out(saved)


@router.delete(
    "/projects/{project_id}/context/profile",
    response_model=ProjectProfileOut,
    summary="Borrar el perfil del proyecto",
    responses=_PROFILE_WRITE_ERRORS,
)
def delete_profile(
    project_id: int, user: CurrentUser, db: DbSession, settings: SettingsDep, ctx: Context, if_match: IfMatch = None
) -> ProjectProfileOut:
    """Borra ``profile.md`` (queda solo el perfil de la plantilla o el manifiesto)."""
    access = projects.get_access(db, project_id, user, min_role="editor")
    return _profile_out(profiles.delete_profile(db, settings, access.project, if_match=if_match, actor=user, ctx=ctx))


@router.post(
    "/projects/{project_id}/context/prompt-preview",
    response_model=PromptPreviewOut,
    summary="Vista previa del prompt de clasificación",
    responses={**ERRORS, 422: {"description": "Sin manifiesto o no válido (prompt_preview_invalid)"}},
)
def preview_prompt(
    project_id: int, body: PromptPreviewIn, user: CurrentUser, db: DbSession, settings: SettingsDep
) -> PromptPreviewOut:
    """Los mensajes que recibiría el modelo al clasificar con la plantilla o el manifiesto y el perfil (el borrador
    del formulario o el guardado), **sin llamarlo**."""
    access = projects.get_access(db, project_id, user)
    preview = profiles.preview(
        db,
        settings,
        access.project,
        user,
        catalog=body.catalog,
        template_name=body.template_name,
        profile_markdown=body.profile_markdown,
    )
    return _preview_out(preview)


@router.post(
    "/taxonomy-templates/prompt-preview",
    response_model=PromptPreviewOut,
    summary="Vista previa del prompt de una plantilla",
    responses={**ERRORS, 422: {"description": "Plantilla no válida (template_invalid)"}},
)
def preview_template_prompt(body: TemplatePromptPreviewIn, admin: TemplateManager) -> PromptPreviewOut:
    """Los mensajes que recibiría el modelo con esta plantilla y su perfil (``templates.manage``), sin llamarlo."""
    del admin
    return _preview_out(profiles.template_preview(body.markdown))
