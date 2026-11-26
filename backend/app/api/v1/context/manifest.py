"""Manifiesto de taxonomía del proyecto, sus versiones (Fase 7) y el acceso al sitio aislado."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.api.deps import Context, CurrentSession, CurrentUser, DbSession, SettingsDep
from app.api.v1.context._shared import ERRORS, IfMatch, catalog, front_matter
from app.api.v1.schemas import (
    ManifestVersionDetail,
    ManifestVersionList,
    ManifestVersionOut,
    SiteSessionOut,
    TaxonomyManifestOut,
    TaxonomyMarkdownIn,
)
from app.domain.context import manifest_versions, site
from app.domain.context import service as context
from app.domain.context.errors import SiteNotFoundError
from app.domain.identity.sessions import acting_user
from app.domain.projects import service as projects

router = APIRouter(tags=["context"])


def _manifest_out(manifest: context.Manifest, db: DbSession, project_id: int) -> TaxonomyManifestOut:
    return TaxonomyManifestOut(
        markdown=manifest.markdown,
        error=manifest.error,
        domains=catalog(manifest.info.domains) if manifest.info else [],
        material_types=catalog(manifest.info.material_types) if manifest.info else [],
        front_matter=front_matter(manifest.info),
        etag=manifest.etag,
        last_changed_at=manifest_versions.latest_version_at(db, project_id),
    )


_MANIFEST_WRITE_ERRORS: dict[int | str, dict[str, Any]] = {
    **ERRORS,
    403: {"description": "Rol insuficiente (editor)"},
    409: {
        "description": "Cambió desde que se leyó (manifest_changed), escritura en curso (write_locked) o no es un "
        "fichero normal (manifest_replaced)"
    },
    422: {"description": "Markdown no válido (template_invalid) o destino de solo lectura"},
    428: {"description": "Falta If-Match (etag_required)"},
    503: {"description": "Ubicación no disponible"},
}


@router.get(
    "/projects/{project_id}/context/taxonomy-manifest",
    response_model=TaxonomyManifestOut,
    summary="Manifiesto de taxonomía del proyecto",
    responses={**ERRORS, 409: {"description": "No es un fichero normal (manifest_replaced)"}},
)
def get_manifest(project_id: int, user: CurrentUser, db: DbSession, settings: SettingsDep) -> TaxonomyManifestOut:
    access = projects.get_access(db, project_id, user)
    return _manifest_out(context.read_manifest(settings, access.project), db, project_id)


@router.put(
    "/projects/{project_id}/context/taxonomy-manifest",
    response_model=TaxonomyManifestOut,
    summary="Guardar manifiesto de taxonomía",
    responses=_MANIFEST_WRITE_ERRORS,
)
def put_manifest(
    project_id: int,
    body: TaxonomyMarkdownIn,
    user: CurrentUser,
    db: DbSession,
    settings: SettingsDep,
    ctx: Context,
    if_match: IfMatch = None,
) -> TaxonomyManifestOut:
    """Valida y escribe ``taxonomy_manifest.md`` (lo usa el catálogo «manifiesto»), guardando antes como versión lo
    que había. El mismo texto no escribe ni crea versión."""
    access = projects.get_access(db, project_id, user, min_role="editor")
    saved = context.save_manifest(db, settings, access.project, body.markdown, if_match=if_match, actor=user, ctx=ctx)
    return _manifest_out(saved, db, project_id)


@router.delete(
    "/projects/{project_id}/context/taxonomy-manifest",
    response_model=TaxonomyManifestOut,
    summary="Borrar manifiesto de taxonomía",
    responses={**_MANIFEST_WRITE_ERRORS, 404: {"description": "Sin acceso o sin manifiesto (manifest_not_found)"}},
)
def delete_manifest(
    project_id: int,
    user: CurrentUser,
    db: DbSession,
    settings: SettingsDep,
    ctx: Context,
    if_match: IfMatch = None,
) -> TaxonomyManifestOut:
    """Borra ``taxonomy_manifest.md`` guardando antes su versión (se puede restaurar)."""
    access = projects.get_access(db, project_id, user, min_role="editor")
    deleted = context.delete_manifest(db, settings, access.project, if_match=if_match, actor=user, ctx=ctx)
    return _manifest_out(deleted, db, project_id)


def _version_fields(version: manifest_versions.VersionSummary) -> dict[str, Any]:
    return {
        "id": version.id,
        "created_at": version.created_at,
        "created_by": version.created_by,
        "action": version.action,
        "empty": version.empty,
        "valid": version.valid,
        "domains": version.domains,
        "material_types": version.material_types,
    }


@router.get(
    "/projects/{project_id}/context/taxonomy-manifest/versions",
    response_model=ManifestVersionList,
    summary="Versiones anteriores del manifiesto",
    responses=ERRORS,
)
def list_manifest_versions(project_id: int, user: CurrentUser, db: DbSession) -> ManifestVersionList:
    """Las últimas versiones (lo que había antes de cada cambio), de la más reciente a la más antigua, sin el texto."""
    projects.get_access(db, project_id, user)
    return ManifestVersionList(
        items=[ManifestVersionOut(**_version_fields(v)) for v in manifest_versions.list_versions(db, project_id)],
        limit=manifest_versions.MAX_MANIFEST_VERSIONS,
    )


@router.get(
    "/projects/{project_id}/context/taxonomy-manifest/versions/{version_id}",
    response_model=ManifestVersionDetail,
    summary="Texto de una versión del manifiesto",
    responses={**ERRORS, 404: {"description": "Sin acceso o versión inexistente (manifest_version_not_found)"}},
)
def get_manifest_version(project_id: int, version_id: int, user: CurrentUser, db: DbSession) -> ManifestVersionDetail:
    projects.get_access(db, project_id, user)
    stored = manifest_versions.get_version(db, project_id, version_id)  # 404 si no es de este proyecto
    summary = next(v for v in manifest_versions.list_versions(db, project_id) if v.id == stored.id)
    return ManifestVersionDetail(**_version_fields(summary), markdown=stored.markdown)


@router.post(
    "/projects/{project_id}/context/taxonomy-manifest/versions/{version_id}/restore",
    response_model=TaxonomyManifestOut,
    summary="Restaurar una versión del manifiesto",
    responses={
        **_MANIFEST_WRITE_ERRORS,
        404: {"description": "Sin acceso o versión inexistente (manifest_version_not_found)"},
        422: {"description": "Versión no válida (manifest_version_invalid) o destino de solo lectura"},
    },
)
def restore_manifest_version(
    project_id: int,
    version_id: int,
    user: CurrentUser,
    db: DbSession,
    settings: SettingsDep,
    ctx: Context,
    if_match: IfMatch = None,
) -> TaxonomyManifestOut:
    """Restaura la versión (una «sin manifiesto» borra el fichero), guardando antes lo que había: se puede deshacer."""
    access = projects.get_access(db, project_id, user, min_role="editor")
    restored = context.restore_manifest(
        db, settings, access.project, version_id, if_match=if_match, actor=user, ctx=ctx
    )
    return _manifest_out(restored, db, project_id)


@router.post(
    "/projects/{project_id}/context/site-session",
    response_model=SiteSessionOut,
    summary="Abrir el sitio del contexto",
    responses={**ERRORS, 404: {"description": "Sin sitio construido (site_not_found) o sin acceso"}},
)
def open_site(project_id: int, session: CurrentSession, db: DbSession, settings: SettingsDep) -> SiteSessionOut:
    """URL del sitio aislado con un token ligado a esta sesión y a este proyecto (caduca en una hora, ADR-010)."""
    access = projects.get_access(db, project_id, acting_user(session))
    if not site.site_built(db, access.project):
        raise SiteNotFoundError("El contexto no tiene sitio construido.")
    token, expires_at = site.mint_token(settings, access.project, session)
    return SiteSessionOut(url=f"/site/{token}/", expires_at=expires_at)
