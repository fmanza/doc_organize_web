"""Consumo de IA por ejecución (web 2.1, IA › Uso): qué se registra al cerrar cada run y los agregados del panel.

Las operaciones con IA ya devuelven sus recuentos en ``runs.result`` (``phase_stats``, agentes, borrador, prueba de
clasificación). Al cerrar el run, el runner llama a :func:`record`, que saca una fila por tarea
(:func:`rows_from_result`) y la guarda en ``ai_usage`` (una por run y tarea: si se repite, se actualiza). Registrar el
consumo **nunca** hace fallar un run (el runner captura y registra el error).

El panel agrupa por día en la **hora local** de quien lo mira (D2): el navegador manda su zona IANA y el periodo
(«7 días», «este mes»…) se calcula en esa zona. Hay pocas filas (una por run y tarea), así que se agregan en Python;
así no depende de las funciones de fecha de cada base de datos.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any, Final, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AiUsageRecord, Project, Run

logger = logging.getLogger(__name__)

Period = Literal["7d", "30d", "month", "all"]
PERIODS: Final[tuple[Period, ...]] = ("7d", "30d", "month", "all")
#: Ejecuciones con más tokens que se listan en el panel.
TOP_RUNS: Final = 10


@dataclass(frozen=True)
class UsageRow:
    """Consumo de una tarea en una ejecución (sin texto de documentos ni prompts)."""

    task: str
    model: str | None
    calls: int = 0
    cached: int = 0
    failed: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    tokens_estimated: bool = False

    @property
    def used(self) -> bool:
        return bool(self.calls or self.cached or self.prompt_tokens or self.completion_tokens)


def _int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 0


def _row(task: str, data: dict[str, Any], *, calls: int | None = None) -> UsageRow:
    model = data.get("model")
    return UsageRow(
        task=task,
        model=model[:128] if isinstance(model, str) and model else None,
        calls=_int(data.get("calls")) if calls is None else calls,
        cached=_int(data.get("cached")),
        failed=_int(data.get("failed")),
        prompt_tokens=_int(data.get("prompt_tokens")),
        completion_tokens=_int(data.get("completion_tokens")),
        tokens_estimated=bool(data.get("tokens_estimated")),
    )


def _enabled(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) and value.get("enabled") else None


def rows_from_result(operation: str, result: Any) -> list[UsageRow]:
    """Una fila por tarea de IA que usó ``operation`` según su ``result``; las que no gastaron nada no salen.

    >>> [r.task for r in rows_from_result("context_build", {"ai": {"enabled": True, "calls": 2, "model": "m"}})]
    ['classify']
    >>> rows_from_result("scan", {"documents": 3})
    []
    """
    if not isinstance(result, dict):
        return []
    found: list[UsageRow] = []
    if operation == "context_build":
        if (ai := _enabled(result.get("ai"))) is not None:
            found.append(_row("classify", ai))
        if (enrich := _enabled(result.get("ai_enrichment"))) is not None:
            found.append(_row("enrich", enrich))
        if (semantic := _enabled(result.get("semantic"))) is not None:
            found.append(_row("embed", semantic, calls=_int(semantic.get("embedded"))))
    elif operation == "taxonomy_draft" and isinstance(result.get("manifest_markdown"), str):
        cached = bool(result.get("cached"))
        row = _row("taxonomy_design", result, calls=0 if cached else 1)
        found.append(UsageRow(**{**vars(row), "cached": 1 if cached else 0}))
    elif operation in ("taxonomy_agent", "context_review_agent"):
        found.append(_row("agent", result, calls=_int(result.get("steps"))))
    elif operation == "context_dry_run" and isinstance(result.get("ai"), dict):
        ai = result["ai"]
        if ai.get("scope") not in (None, "off"):
            found.append(_row("classify", ai))
    return [row for row in found if row.used]


def record(db: Session, run: Run, project: Project | None, result: dict[str, Any] | None) -> int:
    """Guarda el consumo de ``run`` (una fila por tarea; si ya estaba, la actualiza). Devuelve las filas escritas.

    No hace ``commit``: lo hace quien llama.
    """
    rows = rows_from_result(run.operation, result)
    if not rows:
        return 0
    existing = {item.task: item for item in db.scalars(select(AiUsageRecord).where(AiUsageRecord.run_id == run.id))}
    now = datetime.now(UTC)
    for row in rows:
        item = existing.get(row.task) or AiUsageRecord(run_id=run.id, task=row.task, operation=run.operation)
        item.created_at = now
        item.tenant_id = project.tenant_id if project is not None else None
        item.project_id = project.id if project is not None else None
        item.project_name = project.name if project is not None else None
        item.model = row.model
        item.calls, item.cached, item.failed = row.calls, row.cached, row.failed
        item.prompt_tokens, item.completion_tokens = row.prompt_tokens, row.completion_tokens
        item.tokens_estimated = row.tokens_estimated
        db.add(item)
    return len(rows)


def for_run(db: Session, run_id: str) -> list[AiUsageRecord]:
    """El consumo registrado de un run, en orden de tarea."""
    return list(db.scalars(select(AiUsageRecord).where(AiUsageRecord.run_id == run_id).order_by(AiUsageRecord.task)))


# --- agregados del panel --------------------------------------------------------------------------------------------


def zone(name: str | None) -> ZoneInfo:
    """La zona IANA ``name`` si es válida; si no, UTC."""
    if name:
        try:
            return ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError):
            pass
    return ZoneInfo("UTC")


def period_bounds(period: Period, tz: ZoneInfo, now: datetime) -> tuple[datetime | None, datetime]:
    """Inicio (``None`` en «todo») y fin del periodo, en UTC; «7 días» y «30 días» cuentan hoy, en la zona ``tz``."""
    local_today = now.astimezone(tz).date()
    if period == "all":
        return None, now
    if period == "month":
        first = local_today.replace(day=1)
    else:
        first = local_today - timedelta(days=(7 if period == "7d" else 30) - 1)
    start = datetime(first.year, first.month, first.day, tzinfo=tz).astimezone(UTC)
    return start, now


@dataclass
class Totals:
    runs: int = 0
    calls: int = 0
    cached: int = 0
    failed: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    tokens_estimated: bool = False
    _runs: set[str] = field(default_factory=set, repr=False)

    def add(self, item: AiUsageRecord) -> None:
        self._runs.add(item.run_id or f"#{item.id}")
        self.runs = len(self._runs)
        self.calls += item.calls
        self.cached += item.cached
        self.failed += item.failed
        self.prompt_tokens += item.prompt_tokens
        self.completion_tokens += item.completion_tokens
        self.tokens_estimated = self.tokens_estimated or item.tokens_estimated


@dataclass(frozen=True)
class RunUsage:
    run_id: str | None
    created_at: datetime
    operation: str
    project_id: int | None
    project_name: str | None
    totals: Totals


@dataclass
class Summary:
    period: Period
    timezone: str
    start: datetime | None
    end: datetime
    totals: Totals
    by_task: dict[str, Totals]
    by_model: dict[str, Totals]
    by_project: dict[tuple[int | None, str | None], Totals]
    by_day: dict[date, Totals]
    top_runs: list[RunUsage]


def _items(db: Session, start: datetime | None, end: datetime) -> Iterable[AiUsageRecord]:
    query = select(AiUsageRecord).where(AiUsageRecord.created_at <= end)
    if start is not None:
        query = query.where(AiUsageRecord.created_at >= start)
    return db.scalars(query.order_by(AiUsageRecord.created_at))


#: Días como mucho que se rellenan con ceros en «todo» (más allá, solo los días con consumo).
MAX_FILLED_DAYS: Final = 400


def _every_day(by_day: dict[date, Totals], start: datetime | None, end: datetime, tz: ZoneInfo) -> dict[date, Totals]:
    """Los días del periodo en orden, con ceros en los que no hubo consumo: el gráfico no junta días separados."""
    if not by_day and start is None:
        return {}
    last = end.astimezone(tz).date()
    first = start.astimezone(tz).date() if start is not None else min(by_day)
    if (last - first).days >= MAX_FILLED_DAYS:
        return dict(sorted(by_day.items()))
    days = (first + timedelta(days=offset) for offset in range((last - first).days + 1))
    return {day: by_day.get(day, Totals()) for day in days}


def summary(db: Session, *, period: Period, tz_name: str | None, now: datetime | None = None) -> Summary:
    """Agregados de ``ai_usage`` en el periodo: totales, por tarea, modelo, proyecto y día local, y los runs que más
    tokens gastaron."""
    tz = zone(tz_name)
    current = now or datetime.now(UTC)
    start, end = period_bounds(period, tz, current)
    totals = Totals()
    by_task: dict[str, Totals] = defaultdict(Totals)
    by_model: dict[str, Totals] = defaultdict(Totals)
    by_project: dict[tuple[int | None, str | None], Totals] = defaultdict(Totals)
    by_day: dict[date, Totals] = defaultdict(Totals)
    runs: dict[str, RunUsage] = {}
    for item in _items(db, start, end):
        created = item.created_at if item.created_at.tzinfo else item.created_at.replace(tzinfo=UTC)
        totals.add(item)
        by_task[item.task].add(item)
        by_model[item.model or ""].add(item)
        by_project[(item.project_id, item.project_name)].add(item)
        by_day[created.astimezone(tz).date()].add(item)
        key = item.run_id or f"#{item.id}"
        if key not in runs:
            runs[key] = RunUsage(item.run_id, created, item.operation, item.project_id, item.project_name, Totals())
        runs[key].totals.add(item)
    top = sorted(
        runs.values(),
        key=lambda run: run.totals.prompt_tokens + run.totals.completion_tokens,
        reverse=True,
    )[:TOP_RUNS]
    return Summary(
        period=period,
        timezone=tz.key,
        start=start,
        end=end,
        totals=totals,
        by_task=dict(by_task),
        by_model=dict(by_model),
        by_project=dict(by_project),
        by_day=_every_day(by_day, start, end, tz),
        top_runs=[run for run in top if run.totals.prompt_tokens + run.totals.completion_tokens > 0],
    )
