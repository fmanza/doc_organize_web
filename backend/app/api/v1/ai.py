"""IA (Fase 8): ``/admin/ai-settings`` y ``/admin/ai-usage`` (admin de instancia) y ``/ai/status`` (cualquier usuario).

Ninguna respuesta lleva un secreto: los campos secretos solo dicen que están configurados y su ``hint`` (ADR-004).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query

from app.api.deps import AdminUser, Context, CurrentUser, DbSession, SettingsDep
from app.api.v1.schemas import (
    AiFamilyOut,
    AiFamilyUpdate,
    AiFieldOut,
    AiSettingsOut,
    AiStatusOut,
    AiUsageItemOut,
    AiUsageOut,
    AiUsageSourceOut,
)
from app.core import crypto
from app.domain.ai import settings as ai_settings
from app.domain.ai import usage as ai_usage
from app.domain.ai.settings import FamilyView

router = APIRouter(tags=["ai"])

_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"description": "No autenticado"},
    403: {"description": "Sin rol de administrador o token CSRF no válido"},
}


def _family_out(view: FamilyView) -> AiFamilyOut:
    return AiFamilyOut(
        key=view.key,
        configured=view.configured,
        fields=[
            AiFieldOut(
                name=f.name,
                env_var=f.env_var,
                secret=f.secret,
                required=f.required,
                source=f.source,
                value=f.value,
                hint=f.hint,
                undecryptable=f.undecryptable,
            )
            for f in view.fields
        ],
    )


@router.get("/admin/ai-settings", response_model=AiSettingsOut, summary="Ver la configuración de IA", responses=_ERRORS)
def get_ai_settings(_: AdminUser, db: DbSession, settings: SettingsDep) -> AiSettingsOut:
    """Las 5 familias con el origen de cada campo (``db``, ``env`` o ``none``), sin secretos."""
    return AiSettingsOut(
        encryption_configured=crypto.is_configured(settings),
        families=[_family_out(view) for view in ai_settings.list_families(db, settings)],
    )


@router.put(
    "/admin/ai-settings/{family}",
    response_model=AiFamilyOut,
    summary="Cambiar una familia de IA",
    responses={
        **_ERRORS,
        404: {"description": "Familia desconocida (``ai_family_not_found``)"},
        409: {"description": "Cifrado no configurado (``encryption_not_configured``)"},
        422: {"description": "Campo ajeno o valor no válido (``ai_setting_invalid``)"},
    },
)
def put_ai_family(
    family: str, body: AiFamilyUpdate, admin: AdminUser, db: DbSession, settings: SettingsDep, ctx: Context
) -> AiFamilyOut:
    """Guarda o borra campos (ausente = no se toca; ``null`` o ``""`` = borrar) y lo audita sin valores secretos."""
    view = ai_settings.update_family(db, family, body.fields, settings=settings, actor=admin, ctx=ctx)
    ai_usage.clear_cache()
    return _family_out(view)


@router.get("/ai/status", response_model=AiStatusOut, summary="Familias de IA configuradas", responses=_ERRORS)
def get_ai_status(_: CurrentUser, db: DbSession, settings: SettingsDep) -> AiStatusOut:
    """Si cada familia tiene sus campos obligatorios: activa la IA en la página de contexto."""
    return AiStatusOut(families=ai_settings.configured_families(db, settings))


@router.get("/admin/ai-usage", response_model=AiUsageOut, summary="Uso y coste de IA", responses=_ERRORS)
def get_ai_usage(
    _: AdminUser,
    db: DbSession,
    settings: SettingsDep,
    refresh: Annotated[bool, Query(description="Saltar la caché (como mucho una vez cada 30 s)")] = False,
) -> AiUsageOut:
    """Uso del periodo actual de LiteLLM y de GitHub Copilot (caché de 5 minutos por fuente)."""
    sources: list[AiUsageSourceOut] = []
    for entry in ai_usage.usage(db, settings, refresh=refresh):
        report = entry.report
        items = [AiUsageItemOut(**vars(item)) for item in report.items] if report else []
        costs = [item.cost_usd for item in items if item.cost_usd is not None]
        sources.append(
            AiUsageSourceOut(
                source=entry.source,
                configured=entry.configured,
                fetched_at=entry.fetched_at,
                cached=entry.cached,
                period_start=report.period_start if report else None,
                period_end=report.period_end if report else None,
                total_cost_usd=round(sum(costs), 6) if costs else None,
                items=items,
                error=entry.error,
            )
        )
    return AiUsageOut(sources=sources)
