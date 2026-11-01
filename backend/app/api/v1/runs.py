"""``/api/v1/runs``: historial, detalle, cancelación, progreso por SSE y descarga de artefactos (ADR-002, ADR-008).

El SSE (``GET /runs/{id}/events``) lee los eventos persistidos en ``run_events``: se reanuda con ``Last-Event-ID`` (o
``?after=``), envía ``: keep-alive`` cada 15 s, revalida la sesión cada minuto y se cierra tras el evento ``end``. Cada
usuario puede tener como mucho ``MAX_STREAMS_PER_USER`` conexiones abiertas (429).
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
import weakref
from collections.abc import AsyncIterator
from typing import Annotated, Any, Final, cast

from fastapi import APIRouter, Header, Query, Request, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from starlette.concurrency import run_in_threadpool

from app.api.deps import Context, CurrentUser, DbSession, SettingsDep
from app.api.v1.schemas import (
    MAX_PAGE_SIZE,
    ArtifactOut,
    Operation,
    RunBrief,
    RunOut,
    RunPage,
    RunProgress,
    RunStatus,
    ScanErrorOut,
    ScanErrorPage,
)
from app.core.errors import AppError
from app.db.models import ACTIVE_RUN_STATUSES, MemberRole, ProjectMember, Run, User
from app.db.session import get_engine
from app.domain.identity.sessions import resolve_session
from app.domain.runs import events, service
from app.domain.runs.errors import ArtifactGoneError, ArtifactNotFoundError, RunNotFoundError
from app.domain.scan import scan_errors
from app.workspace import runs as workspace

router = APIRouter(prefix="/runs", tags=["runs"])

MAX_STREAMS_PER_USER: Final = 5
POLL_SECONDS: Final = 1.0
KEEPALIVE_SECONDS: Final = 15.0
SESSION_CHECK_SECONDS: Final = 60.0
#: Tipos de contenido que se sirven tal cual; cualquier otro se descarga como binario.
SAFE_CONTENT_TYPES: Final = frozenset({"text/plain", "application/json", "application/zip", "text/csv"})

_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"description": "No autenticado"},
    404: {"description": "Ejecución no encontrada (o sin acceso)"},
}

_streams: dict[int, int] = {}
_streams_lock = threading.Lock()


class TooManyStreamsError(AppError):
    """Demasiadas conexiones SSE abiertas por el mismo usuario."""

    status = 429
    title = "Demasiadas conexiones de progreso abiertas"
    code = "too_many_streams"


def _can_cancel(run: Run, user: User, role: MemberRole | None) -> bool:
    if run.status not in ACTIVE_RUN_STATUSES:
        return False
    return user.role == "admin" or run.created_by == user.id or role == "owner"


def run_out(
    db: Session, run: Run, user: User, role: MemberRole | None, *, names: dict[int, str] | None = None
) -> RunOut:
    """Respuesta HTTP de un run."""
    if names is None:
        names = service.project_names(db, {run.project_id} if run.project_id is not None else set())
    return RunOut(
        id=run.id,
        project_id=run.project_id,
        project_name=names.get(run.project_id) if run.project_id is not None else None,
        operation=run.operation,
        queue=run.queue,
        status=run.status,
        is_write=run.is_write,
        params=run.params,
        progress=RunProgress.model_validate(run.progress) if run.progress else None,
        result=run.result,
        error_code=run.error_code,
        error_message=run.error_message,
        cancel_requested=run.cancel_requested,
        created_by_username=run.created_by_username,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        workspace_purged=run.workspace_purged_at is not None,
        artifacts=[ArtifactOut.model_validate(a) for a in run.artifacts],
        can_cancel=_can_cancel(run, user, role),
    )


@router.get("", response_model=RunPage, summary="Historial de ejecuciones", responses={401: _ERRORS[401]})
def list_runs(
    user: CurrentUser,
    db: DbSession,
    project_id: Annotated[int | None, Query(ge=1)] = None,
    status_: Annotated[RunStatus | None, Query(alias="status")] = None,
    operation: Annotated[Operation | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> RunPage:
    """Runs de los proyectos visibles, más recientes primero (agrupados por ejecución)."""
    rows, total = service.list_runs(
        db, user, project_id=project_id, status=status_, operation=operation, limit=limit, offset=offset
    )
    names = service.project_names(db, {r.project_id for r in rows if r.project_id is not None})
    roles = _roles(db, user, {r.project_id for r in rows if r.project_id is not None})
    items = [run_out(db, r, user, roles.get(r.project_id) if r.project_id else None, names=names) for r in rows]
    return RunPage(items=items, total=total)


def _roles(db: Session, user: User, project_ids: set[int]) -> dict[int, MemberRole]:
    if user.role == "admin":
        return dict.fromkeys(project_ids, "owner")
    rows = db.execute(
        select(ProjectMember.project_id, ProjectMember.role).where(
            ProjectMember.user_id == user.id, ProjectMember.project_id.in_(project_ids)
        )
    )
    return {project_id: cast(MemberRole, role) for project_id, role in rows}


@router.get("/{run_id}", response_model=RunOut, summary="Ver ejecución", responses=_ERRORS)
def get_run(run_id: str, user: CurrentUser, db: DbSession) -> RunOut:
    """Estado, progreso, resultado y artefactos."""
    run, role = service.get_run(db, run_id, user)
    return run_out(db, run, user, role)


@router.get("/{run_id}/scan-errors", response_model=ScanErrorPage, summary="Errores de un escaneo", responses=_ERRORS)
def list_scan_errors(
    run_id: str,
    user: CurrentUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ScanErrorPage:
    """Documentos que no se pudieron convertir en este run (vacío si no es un escaneo)."""
    run, _ = service.get_run(db, run_id, user)
    rows, total = scan_errors.run_errors(db, run.id, limit=limit, offset=offset)
    return ScanErrorPage(
        run=RunBrief.model_validate(run), items=[ScanErrorOut.model_validate(r) for r in rows], total=total
    )


@router.post(
    "/{run_id}/cancel",
    response_model=RunOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Cancelar ejecución",
    responses={
        **_ERRORS,
        403: {"description": "No la lanzaste ni eres propietario"},
        409: {"description": "Ya terminó"},
    },
)
def cancel_run(run_id: str, user: CurrentUser, db: DbSession, ctx: Context) -> RunOut:
    """Cancela un run en cola o pide parar uno en marcha (el worker lo para en el siguiente punto seguro)."""
    run, role = service.get_run(db, run_id, user)
    return run_out(db, service.cancel(db, run, role=role, actor=user, ctx=ctx), user, role)


@router.get(
    "/{run_id}/artifacts/{artifact_id}",
    response_class=FileResponse,
    summary="Descargar artefacto",
    responses={**_ERRORS, 410: {"description": "Purgado por la retención"}},
)
def download_artifact(run_id: str, artifact_id: int, user: CurrentUser, db: DbSession, settings: SettingsDep) -> Any:
    """Descarga un fichero del run como adjunto."""
    run, _ = service.get_run(db, run_id, user)
    artifact = service.get_artifact(run, artifact_id)
    if run.workspace_purged_at is not None:
        raise ArtifactGoneError()
    path = workspace.artifact_path(settings, run.id, artifact.rel_path)
    if path is None:
        raise ArtifactNotFoundError()
    media_type = artifact.content_type if artifact.content_type in SAFE_CONTENT_TYPES else "application/octet-stream"
    return FileResponse(
        path,
        media_type=media_type,
        filename=artifact.name,
        content_disposition_type="attachment",
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"},
    )


# --- SSE ---------------------------------------------------------------------------------------------------------


class _StreamSlot:
    """Plaza de conexión SSE de un usuario; se libera una sola vez (al cerrar el flujo o al recoger el generador si
    el cliente se fue antes de empezar a leerlo)."""

    def __init__(self, user_id: int) -> None:
        with _streams_lock:
            if _streams.get(user_id, 0) >= MAX_STREAMS_PER_USER:
                raise TooManyStreamsError()
            _streams[user_id] = _streams.get(user_id, 0) + 1
        self.user_id = user_id
        self._released = False

    def release(self) -> None:
        with _streams_lock:
            if not self._released:
                self._released = True
                _streams[self.user_id] = max(0, _streams.get(self.user_id, 0) - 1)


def _read(run_id: str, last_seq: int) -> tuple[list[tuple[int, str, str]], bool]:
    """Eventos nuevos ya formateados y si el run ha terminado.

    De los ``progress`` de cada lote solo se envía el último: al abrir el detalle de un run largo no se reenvían miles
    de progresos ya superados (el ``id`` sigue avanzando, así que la reanudación no cambia).
    """
    with sessionmaker(bind=get_engine())() as db:
        found = events.after(db, run_id, last_seq)
        last_progress = max((e.seq for e in found if e.type == "progress"), default=None)
        batch = [
            (e.seq, e.type, json.dumps({**e.data, "ts": e.ts.isoformat()}, ensure_ascii=False))
            for e in found
            if e.type != "progress" or e.seq == last_progress
        ]
        run = db.get(Run, run_id)
        finished = run is None or run.status not in ACTIVE_RUN_STATUSES
    return batch, finished


def _still_allowed(token: str | None, settings: Any, run_id: str) -> bool:
    """La sesión sigue viva y su usuario sigue viendo el run (p. ej. no lo han quitado del proyecto)."""
    if not token:
        return False
    with sessionmaker(bind=get_engine())() as db:
        session = resolve_session(db, token, settings)
        if session is None:
            return False
        try:
            service.get_run(db, run_id, session.user)
        except RunNotFoundError:
            return False
        return True


@router.get(
    "/{run_id}/events",
    response_class=StreamingResponse,
    summary="Progreso en vivo (SSE)",
    responses={
        **_ERRORS,
        200: {"content": {"text/event-stream": {}}, "description": "Flujo de eventos del run"},
        429: {"description": "Demasiadas conexiones abiertas"},
    },
)
def run_events(
    run_id: str,
    request: Request,
    user: CurrentUser,
    db: DbSession,
    settings: SettingsDep,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
    after: Annotated[int | None, Query(ge=0, description="Último evento recibido (si no hay Last-Event-ID)")] = None,
) -> StreamingResponse:
    """Eventos ``status``, ``progress``, ``log``, ``artifact`` y ``end`` del run (``id`` = número de evento)."""
    run, _ = service.get_run(db, run_id, user)
    run_id = run.id
    # El flujo puede durar horas: la sesión de BD de la petición se libera ya (si no, cada flujo retendría una
    # conexión del pool hasta cerrarse). El flujo lee con sesiones propias y cortas.
    db.close()
    start = after or 0
    if last_event_id and last_event_id.isdigit():
        start = int(last_event_id)
    token = request.cookies.get(settings.session_cookie)
    slot = _StreamSlot(user.id)

    async def stream() -> AsyncIterator[str]:
        last = start
        last_sent = last_check = time.monotonic()
        try:
            yield "retry: 3000\n\n"
            while True:
                batch, finished = await run_in_threadpool(_read, run_id, last)
                for seq, type_, data in batch:
                    yield f"id: {seq}\nevent: {type_}\ndata: {data}\n\n"
                    last = seq
                    last_sent = time.monotonic()
                    if type_ == "end":
                        return
                if finished and not batch:
                    return
                now = time.monotonic()
                if now - last_sent >= KEEPALIVE_SECONDS:
                    yield ": keep-alive\n\n"
                    last_sent = now
                if now - last_check >= SESSION_CHECK_SECONDS:
                    if not await run_in_threadpool(_still_allowed, token, settings, run_id):
                        return
                    last_check = now
                if await request.is_disconnected():
                    return
                await asyncio.sleep(POLL_SECONDS)
        finally:
            slot.release()

    iterator = stream()
    weakref.finalize(iterator, slot.release)
    return StreamingResponse(
        iterator,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
