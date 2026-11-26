"""``export_site`` y ``export_ai_bundle``: entrega del contexto (W8, doc_organize 2.0.0rc1 F3/F7).

- Sitio sin conexión: ZIP reproducible (``sitio/``, ``start_server.py`` y ``VER_SITIO.md``) con el contenido de
  terceros neutralizado, comprobado con ``check_site_offline``. Se construye sobre una copia de la carpeta
  reorganizada en el workspace del run: el destino y el sitio que sirve la web no cambian.
- Paquete para IA: ``llms.txt``, un ``.md`` por documento con su ficha y ``context.json``, sin credenciales salvo que un
  administrador lo pida (S-F7-1, validado al encolar).

Los dos son artefactos del run (cuota y retención de las exportaciones). El SHA-256 va en el resultado y en la
auditoría (``project.export_site``/``project.export_ai_bundle``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

from app.db.models import Project
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction
from app.domain.runs.operations import ExportAiBundleParams, ExportSiteParams
from app.domain.runs.results import ExportAiBundleResult, ExportSiteResult
from app.integrations import doc_organize as library
from app.integrations.doc_organize.delivery import (
    AiBundleRequest,
    OfflineSiteProblemsError,
    OfflineSiteRequest,
    SiteNotReadyError,
    reorganized_size,
    write_ai_bundle,
    write_offline_site,
)
from app.jobs.context import JobCancelled, JobContext, JobFailed
from app.jobs.operations.common import WORKER_CONTEXT, require_project
from app.jobs.operations.context import context_folders
from app.jobs.operations.export import EXPORT_DIR, _check_room, _file_name, _progress, _request

SITE_BUILD_DIR: Final = "site_build"
NO_CONTEXT: Final = "El proyecto no tiene contexto: constrúyelo primero."
NOT_READY: Final = "El contexto no tiene carpeta reorganizada: reconstrúyelo para poder entregar el sitio."


def _audit(ctx: JobContext, project: Project, action: str, details: dict[str, Any]) -> None:
    with ctx.session_factory() as db:
        audit.record(
            db,
            action=action,
            ctx=WORKER_CONTEXT,
            actor_id=ctx.created_by,
            target_type="project",
            target_id=project.id,
            details={"run_id": ctx.run_id, **details},
        )
        db.commit()


def run_site(ctx: JobContext, params: ExportSiteParams, project: Project | None) -> ExportSiteResult:
    """Construye el sitio sin conexión, lo comprueba y deja su ZIP como artefacto, con su SHA-256."""
    project = require_project(project)
    request = _request(ctx, project)
    ctx.progress("preview", 0, None)
    try:
        size = reorganized_size(request)
    except library.ContextMissingError:
        raise JobFailed("context_not_found", NO_CONTEXT) from None
    except SiteNotReadyError:
        raise JobFailed("site_not_ready", NOT_READY) from None
    ctx.workdir.mkdir(parents=True, exist_ok=True)
    _check_room(ctx, 3 * size)  # la copia, el sitio construido y el ZIP
    name = _file_name(project, "-sitio.zip")
    target: Path = ctx.workdir / EXPORT_DIR / name
    target.parent.mkdir(exist_ok=True)
    site = OfflineSiteRequest(
        export=request,
        build_root=ctx.workdir / SITE_BUILD_DIR,
        llms_txt=params.llms_txt,
        redact=project.ai_redact_credentials,
        timeout=float(ctx.settings.context_site_timeout_seconds),
    )
    try:
        result = write_offline_site(
            target,
            site,
            on_phase=lambda phase: ctx.progress(phase, 0, None),
            on_progress=_progress(ctx),
            is_cancelled=lambda: ctx.cancelled,
        )
    except library.ExportCancelled:
        raise JobCancelled() from None
    except library.ContextMissingError:
        raise JobFailed("context_not_found", NO_CONTEXT) from None
    except SiteNotReadyError:
        raise JobFailed("site_not_ready", NOT_READY) from None
    except OfflineSiteProblemsError as exc:
        target.unlink(missing_ok=True)
        for problem in exc.problems[:20]:
            ctx.log(problem, level="warning")
        raise JobFailed(
            "site_offline_invalid",
            f"El sitio no se puede entregar sin conexión ({len(exc.problems)} problemas; están en el log).",
        ) from None
    except (library.DocOrganizeOperationError, OSError):
        target.unlink(missing_ok=True)
        raise JobFailed("export_failed", "No se pudo construir o empaquetar el sitio sin conexión.") from None
    ctx.add_artifact(f"{EXPORT_DIR}/{name}", name=name)
    _audit(
        ctx,
        project,
        AuditAction.PROJECT_EXPORT_SITE,
        {
            "sha256": result["sha256"],
            "zip_size_bytes": result["zip_size_bytes"],
            "llms_txt": params.llms_txt,
            "redact_credentials": site.redact,
        },
    )
    neutralized = result.pop("neutralized")
    if neutralized:
        detail = ", ".join(f"{kind}: {count}" for kind, count in sorted(neutralized.items()))
        ctx.log(f"Contenido de terceros neutralizado en {result['neutralized_pages']} páginas ({detail}).")
    ctx.log(f"Sitio sin conexión: {name} · SHA-256 {result['sha256']}")
    ctx.progress("done", 1, 1)
    return ExportSiteResult.model_validate({**result, "file_name": name, "redact_credentials": site.redact})


def run_ai_bundle(ctx: JobContext, params: ExportAiBundleParams, project: Project | None) -> ExportAiBundleResult:
    """Escribe el paquete para IA como artefacto, con su SHA-256."""
    project = require_project(project)
    request = _request(ctx, project)
    _, folders, _ = context_folders(ctx, project)
    name = _file_name(project, "-ia.zip")
    target: Path = ctx.workdir / EXPORT_DIR / name
    target.parent.mkdir(parents=True, exist_ok=True)
    bundle = AiBundleRequest(
        export=request,
        roots=library.context.scan_roots(folders),
        include_text=params.include_text,
        current_only=params.current_only,
        redact=params.redact,
        max_file_chars=params.max_file_chars,
        max_full_chars=params.max_full_chars,
    )
    ctx.progress("export", 0, None)
    try:
        stats = write_ai_bundle(target, bundle, on_progress=_progress(ctx), is_cancelled=lambda: ctx.cancelled)
    except library.ExportCancelled:
        raise JobCancelled() from None
    except library.ContextMissingError:
        raise JobFailed("context_not_found", NO_CONTEXT) from None
    except (library.DocOrganizeOperationError, OSError):
        target.unlink(missing_ok=True)
        raise JobFailed("export_failed", "No se pudo escribir el paquete para IA.") from None
    ctx.add_artifact(f"{EXPORT_DIR}/{name}", name=name)
    options = params.model_dump(exclude={"operation"})
    _audit(
        ctx,
        project,
        AuditAction.PROJECT_EXPORT_AI_BUNDLE,
        {"sha256": stats["sha256"], "documents": stats["documents"], **options},
    )
    if not params.redact:
        ctx.log("Paquete SIN redactar credenciales (lo pidió un administrador).", level="warning")
    ctx.log(f"Paquete para IA: {name} · SHA-256 {stats['sha256']}")
    ctx.progress("done", 1, 1)
    return ExportAiBundleResult.model_validate(
        {**stats, "file_name": name, "zip_size_bytes": target.stat().st_size, **options}
    )
