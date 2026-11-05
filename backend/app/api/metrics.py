"""``GET /metrics`` (Fase 10): métricas en formato de texto de Prometheus para el operador.

Existe solo con el secreto ``dow_metrics_token`` y se pide con ``Authorization: Bearer <token>``; sin secreto o con un
token que no casa responde 404 (no delata que exista). Fuera de OpenAPI: no es parte del contrato de la SPA.

Nada identifica a personas ni carpetas: rutas como plantilla, runs por estado/cola/operación, códigos de error de los
runs fallidos (``out_of_memory``, ``timeout``…), workers vivos y tamaño de ``config.db``.
"""

from __future__ import annotations

import hmac
from collections.abc import Iterable
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import __version__
from app.api.deps import DbSession, SettingsDep
from app.core.config import Settings
from app.core.metrics import HttpMetrics, labels
from app.db.models import Run
from app.domain.runs import workers
from app.integrations.doc_organize import library_version

router = APIRouter(include_in_schema=False)

CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"


def require_token(settings: SettingsDep, authorization: Annotated[str | None, Header()] = None) -> None:
    """404 salvo que ``Authorization`` lleve el token de ``dow_metrics_token`` (comparación en tiempo constante)."""
    expected = settings.metrics_token.get_secret_value() if settings.metrics_token is not None else ""
    scheme, _, token = (authorization or "").partition(" ")
    if not expected or scheme.lower() != "bearer" or not hmac.compare_digest(token.encode(), expected.encode()):
        raise HTTPException(404, "Not Found")


def _gauge(name: str, help_text: str, rows: Iterable[tuple[dict[str, str], float]]) -> Iterable[str]:
    yield f"# HELP {name} {help_text}"
    yield f"# TYPE {name} gauge"
    for row_labels, value in rows:
        yield f"{name}{labels(**row_labels)} {value:g}"


def application_metrics(db: Session, settings: Settings) -> Iterable[str]:
    """Métricas de ``config.db``: build, runs, workers y tamaño de la BD."""
    yield from _gauge(
        "dow_build_info",
        "Versión de la aplicación y de doc_organize.",
        [({"version": __version__, "doc_organize": library_version() or "unknown"}, 1)],
    )
    runs = db.execute(
        select(Run.status, Run.queue, Run.operation, func.count()).group_by(Run.status, Run.queue, Run.operation)
    )
    yield from _gauge(
        "dow_runs",
        "Runs por estado, cola y operación.",
        [({"status": s, "queue": q, "operation": o}, n) for s, q, o, n in runs],
    )
    failed = db.execute(select(Run.error_code, func.count()).where(Run.status == "failed").group_by(Run.error_code))
    yield from _gauge(
        "dow_runs_failed",
        "Runs fallidos por código de error (out_of_memory: el worker se quedó sin memoria).",
        [({"code": code or "unknown"}, n) for code, n in failed],
    )
    alive = sum(1 for worker in workers.list_workers(db) if workers.is_alive(worker, settings))
    yield from _gauge("dow_workers_alive", "Workers con latido reciente.", [({}, alive)])
    database = settings.data_dir / "config.db"
    size = database.stat().st_size if database.is_file() else 0
    yield from _gauge("dow_database_bytes", "Tamaño de config.db.", [({}, size)])


@router.get("/metrics", dependencies=[Depends(require_token)], response_class=PlainTextResponse)
def metrics(request: Request, db: DbSession, settings: SettingsDep) -> PlainTextResponse:
    http: HttpMetrics = request.app.state.http_metrics
    body = "\n".join([*http.render(), *application_metrics(db, settings)]) + "\n"
    return PlainTextResponse(body, media_type=CONTENT_TYPE)
