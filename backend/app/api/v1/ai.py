"""IA (Fase 8): ``/admin/ai-settings`` y ``/admin/ai-usage`` (admin de instancia) y ``/ai/status`` (cualquier usuario).

Ninguna respuesta lleva un secreto: los campos secretos solo dicen que están configurados y su ``hint`` (ADR-004).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query

from app.api.deps import Context, CurrentUser, DbSession, InstanceAdmin, SettingsDep
from app.api.v1.schemas import (
    AiFamilyOut,
    AiFamilyUpdate,
    AiFieldOut,
    AiKeyBudgetOut,
    AiLegacyVariableOut,
    AiSettingsOut,
    AiStatusOut,
    AiTestIn,
    AiTestOut,
    AiUsageDayOut,
    AiUsageGroupOut,
    AiUsageItemOut,
    AiUsageLocalOut,
    AiUsageOut,
    AiUsageRunOut,
    AiUsageSourceOut,
    AiUsageTotalsOut,
    DiagnosticCheckOut,
    DiagnosticsIn,
    DiagnosticsOut,
)
from app.core import crypto
from app.domain.ai import connection_test, usage_log
from app.domain.ai import diagnostics as ai_diagnostics
from app.domain.ai import settings as ai_settings
from app.domain.ai import usage as ai_usage
from app.domain.ai.settings import FamilyView
from app.integrations.doc_organize.ai import KeyBudget

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
                task=f.task,
            )
            for f in view.fields
        ],
    )


@router.get("/admin/ai-settings", response_model=AiSettingsOut, summary="Ver la configuración de IA", responses=_ERRORS)
def get_ai_settings(_: InstanceAdmin, db: DbSession, settings: SettingsDep) -> AiSettingsOut:
    """Las familias con el origen de cada campo (``db``, ``env`` o ``none``), sin secretos, y las variables de entorno
    que siguen definidas y ya no se leen (de doc_organize 1.x y de GitHub Copilot)."""
    return AiSettingsOut(
        encryption_configured=crypto.is_configured(settings),
        families=[_family_out(view) for view in ai_settings.list_families(db, settings)],
        legacy_variables=[
            AiLegacyVariableOut(name=name, replacement=replacement)
            for name, replacement in sorted(ai_settings.legacy_variables().items())
        ],
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
    family: str, body: AiFamilyUpdate, admin: InstanceAdmin, db: DbSession, settings: SettingsDep, ctx: Context
) -> AiFamilyOut:
    """Guarda o borra campos (ausente = no se toca; ``null`` o ``""`` = borrar) y lo audita sin valores secretos."""
    view = ai_settings.update_family(db, family, body.fields, settings=settings, actor=admin, ctx=ctx)
    ai_usage.clear_cache()
    return _family_out(view)


@router.post(
    "/admin/ai-settings/{family}/test",
    response_model=AiTestOut,
    summary="Probar la conexión de una familia de IA",
    responses={
        **_ERRORS,
        404: {"description": "Familia desconocida (``ai_family_not_found``)"},
        422: {
            "description": (
                "Campo ajeno o valor no válido (``ai_setting_invalid``), falta un obligatorio (``ai_not_configured``) "
                "u otra URL sin escribir la clave (``secret_required``)"
            )
        },
        429: {"description": "Otra prueba de la familia hace menos de 10 s (``ai_test_too_soon``)"},
    },
)
def probe_ai_family(
    family: str, body: AiTestIn, admin: InstanceAdmin, db: DbSession, settings: SettingsDep, ctx: Context
) -> AiTestOut:
    """Prueba la familia con los valores del formulario encima de los guardados, sin guardar nada.

    Con LiteLLM consulta ``/key/info`` (servidor y clave, sin coste) y, con ``model_check``, envía además una
    clasificación mínima al modelo. Se audita sin valores.
    """
    outcome = connection_test.probe_family(
        db, family, body.fields, model_check=body.model_check, task=body.task, settings=settings, actor=admin, ctx=ctx
    )
    check = outcome.check
    return AiTestOut(
        ok=outcome.ok,
        error=check.error,
        model_access=check.model_access,
        model_checked=check.model_checked,
        task=check.task,
        response_format=check.response_format,
        elapsed_ms=check.elapsed_ms,
        tested_at=outcome.tested_at,
    )


@router.get("/ai/status", response_model=AiStatusOut, summary="Familias de IA configuradas", responses=_ERRORS)
def get_ai_status(_: CurrentUser, db: DbSession, settings: SettingsDep) -> AiStatusOut:
    """Si cada familia tiene sus campos obligatorios y si cada tarea se puede usar: activa la IA en la página de
    contexto."""
    return AiStatusOut(
        families=ai_settings.configured_families(db, settings),
        tasks=ai_settings.configured_tasks(db, settings),
    )


def _budget_out(budget: KeyBudget) -> AiKeyBudgetOut:
    return AiKeyBudgetOut(
        spend=budget.spend,
        max_budget=budget.max_budget,
        remaining=budget.remaining,
        budget_reset_at=budget.budget_reset_at,
    )


def _totals(totals: usage_log.Totals) -> dict[str, Any]:
    return {
        "runs": totals.runs,
        "calls": totals.calls,
        "cached": totals.cached,
        "failed": totals.failed,
        "prompt_tokens": totals.prompt_tokens,
        "completion_tokens": totals.completion_tokens,
        "tokens_estimated": totals.tokens_estimated,
    }


def _by_tokens(groups: list[AiUsageGroupOut]) -> list[AiUsageGroupOut]:
    return sorted(groups, key=lambda group: group.prompt_tokens + group.completion_tokens, reverse=True)


def _local_out(summary: usage_log.Summary) -> AiUsageLocalOut:
    return AiUsageLocalOut(
        period=summary.period,
        timezone=summary.timezone,
        start=summary.start,
        end=summary.end,
        totals=AiUsageTotalsOut(**_totals(summary.totals)),
        by_task=_by_tokens([AiUsageGroupOut(key=key, **_totals(t)) for key, t in summary.by_task.items()]),
        by_model=_by_tokens([AiUsageGroupOut(key=key, **_totals(t)) for key, t in summary.by_model.items()]),
        by_project=_by_tokens(
            [
                AiUsageGroupOut(key=str(pid) if pid is not None else "", label=name, project_id=pid, **_totals(t))
                for (pid, name), t in summary.by_project.items()
            ]
        ),
        by_day=[AiUsageDayOut(day=day, **_totals(t)) for day, t in summary.by_day.items()],
        top_runs=[
            AiUsageRunOut(
                run_id=run.run_id,
                created_at=run.created_at,
                operation=run.operation,
                project_id=run.project_id,
                project_name=run.project_name,
                **_totals(run.totals),
            )
            for run in summary.top_runs
        ],
    )


@router.get("/admin/ai-usage", response_model=AiUsageOut, summary="Uso y coste de IA", responses=_ERRORS)
def get_ai_usage(
    _: InstanceAdmin,
    db: DbSession,
    settings: SettingsDep,
    refresh: Annotated[bool, Query(description="Saltar la caché (como mucho una vez cada 30 s)")] = False,
    period: Annotated[
        usage_log.Period, Query(description="Periodo del consumo registrado: 7 o 30 días, este mes o todo")
    ] = "30d",
    tz: Annotated[
        str | None,
        Query(max_length=64, description="Zona IANA para agrupar por día (la del navegador); UTC si no vale"),
    ] = None,
) -> AiUsageOut:
    """Gasto acumulado y presupuesto de la clave de LiteLLM (caché de 5 minutos) y el consumo por ejecución que
    registra la web (tokens, documentos y caché por tarea, modelo, proyecto y día local)."""
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
                budget=_budget_out(report.budget) if report and report.budget else None,
                error=entry.error,
            )
        )
    return AiUsageOut(sources=sources, local=_local_out(usage_log.summary(db, period=period, tz_name=tz)))


@router.post(
    "/admin/diagnostics",
    response_model=DiagnosticsOut,
    summary="Diagnóstico del entorno",
    responses={
        **_ERRORS,
        429: {"description": "Otro diagnóstico en marcha o hace menos de 30 s (diagnostics_too_soon)"},
        503: {"description": "No terminó a tiempo o falló (diagnostics_failed)"},
    },
)
def run_diagnostics(
    body: DiagnosticsIn, admin: InstanceAdmin, db: DbSession, settings: SettingsDep, ctx: Context
) -> DiagnosticsOut:
    """``check_environment`` de doc_organize en el servidor web (Python, docling y sus modelos, extras, sitio de prueba,
    GPU, LibreOffice, audio y vídeo) y, con ``check_ai``, los modelos de IA de la familia ``litellm``. Puede tardar un
    minuto; se audita sin detalles."""
    report = ai_diagnostics.run(db, settings, check_ai=body.check_ai, actor=admin, ctx=ctx)
    return DiagnosticsOut(
        ok=report.ok,
        checked_at=report.checked_at,
        checks=[DiagnosticCheckOut.model_validate(check, from_attributes=True) for check in report.checks],
    )
