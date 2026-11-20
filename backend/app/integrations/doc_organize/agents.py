"""Agentes de doc_organize 2.0.0rc1 (W7, M8): diseñador de la taxonomía, comprobación por reglas, revisor y auditor.

Solo se llaman desde el subproceso de un job (leen los ``.json`` de todos los documentos o el ``context.json``).
doc_organize se importa dentro de cada función (G15).

Firmas verificadas en el tag ``v2.0.0rc1``::

    RulesCorpus.load(documents, *, roots=None) -> RulesCorpus
    check_taxonomy_rules(manifest, corpus, *, threshold=0.5) -> TaxonomyRulesReport (axes, documents, unreadable;
        to_markdown(), improves_on(base))
    TaxonomyDesignAgent(llm, *, prompts=None, limits=None, threshold=0.5).propose(documents | corpus, *, base=None,
        instructions="", roots=None, cancel_token=None) -> TaxonomyDesignProposal (manifest, rationale, report,
        base_report, run, draft, edits, best, best_report; improves, markdown(body=""))
    AgentLimits(max_steps=12, max_tokens=80_000, max_tool_calls=40, max_tool_result_chars=8_000, answer_retries=1,
        keep_tool_results=None)
    AgentRun(stop_reason, answer, steps, messages, prompt_tokens, completion_tokens, duration_s; finished, tool_calls)

Las claves de los documentos en los informes son las de las decisiones (``scan_roots``): ``<carpeta>/<ruta>``. Los
agentes solo proponen: nada de lo que devuelven se guarda solo (D14).
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Final

from app.integrations.doc_organize.ai import AiConnection, llm_client
from app.integrations.doc_organize.context import (
    CANCEL_POLL_SECONDS,
    TEMPLATE_SOURCE,
    SourceFolder,
    TemplateInvalidError,
    converted_documents,
    scan_roots,
)
from app.integrations.doc_organize.projects import DocOrganizeOperationError

#: Pasos del diseñador como mucho (``AgentLimits.max_steps``); por defecto el de la librería (30).
DEFAULT_DESIGN_STEPS: Final = 30
MAX_DESIGN_STEPS: Final = 60


class NoDocumentsError(Exception):
    """No hay ningún documento convertido legible con el que comprobar o diseñar la taxonomía."""


def _manifest(markdown: str) -> Any:
    from doc_organize import parse_taxonomy_template
    from doc_organize.core.exceptions import TaxonomyTemplateError

    try:
        return parse_taxonomy_template(markdown, source=TEMPLATE_SOURCE)
    except TaxonomyTemplateError as exc:
        raise TemplateInvalidError(str(exc)) from None


def _report(report: Any) -> dict[str, Any] | None:
    """``TaxonomyRulesReport`` en JSON (con su tabla en Markdown), o ``None``."""
    if report is None:
        return None
    data: dict[str, Any] = report.model_dump(mode="json")
    data["markdown"] = report.to_markdown()
    data["coverage"] = {axis.axis: axis.coverage for axis in report.axes}
    return data


def _corpus(folders: list[SourceFolder]) -> Any:
    from doc_organize.context.taxonomy_check import RulesCorpus

    documents, _ = converted_documents(folders)
    corpus = asyncio.run(RulesCorpus.load(documents, roots=scan_roots(folders)))
    if not corpus.documents:
        raise NoDocumentsError()
    return corpus


def check_rules(markdown: str, folders: list[SourceFolder], *, threshold: float = 0.5) -> dict[str, Any]:
    """Comprueba un manifiesto por reglas contra todos los documentos convertidos (``check_taxonomy_rules``), sin IA y
    sin guardar nada: cobertura, conflictos, entradas vacías, términos compartidos y palabras clave sin uso.

    Raises:
        TemplateInvalidError: El Markdown no es un manifiesto válido.
        NoDocumentsError: No hay documentos legibles.
    """
    from doc_organize.context.taxonomy_check import check_taxonomy_rules

    manifest = _manifest(markdown)
    report = _report(check_taxonomy_rules(manifest, _corpus(folders), threshold=threshold))
    assert report is not None  # noqa: S101 - check_taxonomy_rules siempre da informe
    return report


@dataclass(frozen=True)
class DesignRequest:
    """Una ejecución del diseñador de la taxonomía."""

    output_root: Path
    folders: list[SourceFolder]
    connection: AiConnection
    base_markdown: str | None = None
    instructions: str = ""
    max_steps: int = DEFAULT_DESIGN_STEPS
    threshold: float = 0.5


def _run_stats(run: Any) -> dict[str, Any]:
    return {
        "stop_reason": str(run.stop_reason),
        "finished": bool(run.finished),
        "steps": len(run.steps),
        "tool_calls": len(run.tool_calls),
        "prompt_tokens": int(run.prompt_tokens),
        "completion_tokens": int(run.completion_tokens),
        "duration_s": round(float(run.duration_s), 1),
    }


def _with_cancel(is_cancelled: Callable[[], bool]) -> tuple[Any, threading.Event]:
    """Un ``CancelToken`` que se cancela cuando ``is_cancelled`` (la cancelación del run) lo dice."""
    from doc_organize import CancelToken

    token = CancelToken()
    stop = threading.Event()

    def _bridge() -> None:
        while not stop.wait(CANCEL_POLL_SECONDS):
            if is_cancelled():
                token.cancel()
                return

    threading.Thread(target=_bridge, name="dow-agent-cancel", daemon=True).start()
    return token, stop


def design_taxonomy(
    request: DesignRequest,
    *,
    on_progress: Callable[[str], None],
    is_cancelled: Callable[[], bool],
) -> dict[str, Any]:
    """Pide al ``TaxonomyDesignAgent`` una propuesta (tarea ``agent``). **No guarda nada**: la propuesta, el mejor
    borrador comprobado y los informes por reglas van en el resultado para que una persona los revise.

    Raises:
        TemplateInvalidError: El manifiesto de partida no es válido.
        NoDocumentsError: No hay documentos legibles.
        DocOrganizeOperationError: Falló el proxy de IA (código sin detalles en el mensaje).
    """
    from doc_organize import PromptRegistry, TaxonomyDesignAgent
    from doc_organize.context.taxonomy_agent import DEFAULT_DESIGN_LIMITS
    from doc_organize.core.exceptions import AiError

    base = _manifest(request.base_markdown) if request.base_markdown is not None else None
    on_progress("agent_corpus")
    corpus = _corpus(request.folders)
    limits = replace(DEFAULT_DESIGN_LIMITS, max_steps=request.max_steps)
    token, stop = _with_cancel(is_cancelled)

    async def _run() -> Any:
        async with llm_client(request.connection) as llm:
            agent = TaxonomyDesignAgent(
                llm, prompts=PromptRegistry(str(request.output_root)), limits=limits, threshold=request.threshold
            )
            return await agent.propose(corpus, base=base, instructions=request.instructions, cancel_token=token)

    on_progress("agent_run")
    try:
        proposal = asyncio.run(_run())
    except AiError as exc:
        raise DocOrganizeOperationError(f"El servicio de IA falló ({type(exc).__name__}).") from None
    finally:
        stop.set()
    best = proposal.best
    best_differs = best is not None and (proposal.manifest is None or best != proposal.manifest)
    from doc_organize.context.taxonomy_templates import render_taxonomy_template

    return {
        **_run_stats(proposal.run),
        "base": request.base_markdown is not None,
        "instructions": bool(request.instructions),
        "max_steps": request.max_steps,
        "documents": len(corpus.documents),
        "improves": proposal.improves,
        "rationale": proposal.rationale,
        "edits": int(proposal.edits),
        "markdown": proposal.markdown(),
        "draft_markdown": render_taxonomy_template(proposal.draft)
        if proposal.manifest is None and proposal.draft
        else None,
        "best_markdown": render_taxonomy_template(best) if best_differs and best is not None else None,
        "base_report": _report(proposal.base_report),
        "report": _report(proposal.report),
        "best_report": _report(proposal.best_report) if best_differs else None,
    }


@dataclass(frozen=True)
class ReviewRequest:
    """Una ejecución del revisor de la clasificación."""

    name: str
    created_at: Any
    output_root: Path
    folders: list[SourceFolder]
    connection: AiConnection
    max_items: int = 20
    max_steps: int = 40
    instructions: str = ""


def _load_context(output_root: Path, name: str, created_at: Any) -> Any:
    from doc_organize import ContextRegistry
    from doc_organize.core.exceptions import ContextError

    from app.integrations.doc_organize.context import _project

    try:
        return asyncio.run(ContextRegistry().load_context(_project(name, output_root, created_at)))
    except (ContextError, OSError, ValueError) as exc:
        raise DocOrganizeOperationError("No se pudo leer el contexto del proyecto.") from exc


def review(request: ReviewRequest, *, is_cancelled: Callable[[], bool]) -> dict[str, Any]:
    """Pide al ``ReviewAgent`` (tarea ``agent``) propuestas para los primeros ``max_items`` documentos de la cola de
    revisión. Las propuestas **no se aplican** (D14): van en el resultado para guardarlas como pendientes.

    Raises:
        DocOrganizeOperationError: Sin contexto legible, sin ejes de taxonomía o fallo del proxy de IA.
    """
    from doc_organize import PromptRegistry, ReviewAgent
    from doc_organize.context.review_agent import DEFAULT_REVIEW_LIMITS
    from doc_organize.core.exceptions import AiError

    context = _load_context(request.output_root, request.name, request.created_at)
    if not context.taxonomy_axes:
        raise DocOrganizeOperationError("El revisor necesita un contexto construido con plantilla o manifiesto.")
    limits = replace(DEFAULT_REVIEW_LIMITS, max_steps=request.max_steps)
    token, stop = _with_cancel(is_cancelled)

    async def _run() -> Any:
        async with llm_client(request.connection) as llm:
            agent = ReviewAgent(llm, prompts=PromptRegistry(str(request.output_root)), limits=limits)
            return await agent.propose(
                context,
                max_items=request.max_items,
                roots=scan_roots(request.folders),
                instructions=request.instructions,
                cancel_token=token,
            )

    try:
        result = asyncio.run(_run())
    except AiError as exc:
        raise DocOrganizeOperationError(f"El servicio de IA falló ({type(exc).__name__}).") from None
    except ValueError as exc:
        raise DocOrganizeOperationError(str(exc)) from None
    finally:
        stop.set()
    return {
        **_run_stats(result.run),
        "max_steps": request.max_steps,
        "max_items": request.max_items,
        "reviewed": len({item.document_key for item in result.items}),
        "summary": result.summary,
        "proposals": [proposal.model_dump(mode="json") for proposal in result.proposals],
    }


def audit(output_root: Path, *, name: str, created_at: Any) -> dict[str, Any]:
    """Informe del auditor (``audit_taxonomy``), sin IA: estadísticas por eje y propuestas sobre el catálogo.

    Raises:
        DocOrganizeOperationError: Sin contexto legible.
    """
    from doc_organize import audit_taxonomy

    report = audit_taxonomy(_load_context(output_root, name, created_at))
    data: dict[str, Any] = report.model_dump(mode="json")
    data["markdown"] = report.to_markdown()
    return data
