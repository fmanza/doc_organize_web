"""Operaciones ``context_build`` y ``context_delete`` (Fase 7) en el propio proceso, con ``ContextBuilder``,
``Reorganizer`` y ``SiteGenerator`` reales de doc_organize 0.13.0 (sin Docling) y documentos sintéticos: conversiones
falsas (``.md`` + ``.json`` con ``title``/``chunks``) en ``Conversión/``, proyección en la BD con rutas relativas,
avisos sin rutas del contenedor, colisiones (G30), enlaces (G27) y borrado con vista previa."""

from __future__ import annotations

import json
import os
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from doc_organize import CacheEntry
from doc_organize.core.models import ConversionStatus, DocumentStatus
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.db.models import AuditEntry, ContextDocument, Location, Project, ProjectContext, Run, RunEvent
from app.db.session import get_engine
from app.domain.documents.outputs import output_paths
from app.domain.projects.service import state_dir
from app.domain.runs.operations import RUN_PARAMS
from app.domain.scan.state import CONVERSION_DIR, folder_cache
from app.jobs import queue
from app.jobs.context import JobCancelled, JobContext, JobFailed
from app.jobs.operations import context as operation
from tests.api.test_context import TEMPLATE
from tests.api.test_documents import write_cache
from tests.conftest import project_payload

#: Documentos sintéticos: (carpeta, ruta, título, texto).
FILES = [
    ("2024", "factura.txt", "Factura de enero", "facturas de enero: importe e iva de las facturas"),
    ("2024", "obras/informe.txt", "Informe de obra", "informes técnicos de la obra y otros informes"),
    ("2025", "factura.txt", "Factura de febrero", "facturas de febrero y sus facturas"),
    ("2025", "receta.txt", "Receta", "harina huevos azúcar"),
]


def _entry(path: Path) -> CacheEntry:
    return CacheEntry(
        file_path=str(path),
        sha256_hash="0" * 64,
        timestamp=time.time(),
        status=DocumentStatus.NEW,
        conversion_status=ConversionStatus.SUCCESS,
    )


@pytest.fixture
def project(user_client: TestClient, project_locations: dict[str, Location], migrated: Settings) -> Project:
    source = migrated.locations_root / "origen"
    (source / "2024" / "factura.txt").unlink()
    for folder, relative, _, text in FILES:
        original = source / folder / relative
        original.parent.mkdir(parents=True, exist_ok=True)
        original.write_text(text, encoding="utf-8")
    response = user_client.post(
        "/api/v1/projects", json=project_payload(project_locations, source_subpaths=["2024", "2025"])
    )
    assert response.status_code == 201, response.text
    with sessionmaker(bind=get_engine(), expire_on_commit=False)() as db:
        loaded = db.get(Project, response.json()["id"])
        assert loaded is not None
        _ = (loaded.source_location, loaded.destination_location)
        db.expunge(loaded)
    conversion = migrated.locations_root / "salidas" / "Proyecto A" / CONVERSION_DIR
    for folder, relative, title, text in FILES:
        paths = output_paths(folder, relative)
        (conversion / paths.markdown).parent.mkdir(parents=True, exist_ok=True)
        (conversion / paths.markdown).write_text(f"# {title}\n\n{text}\n", encoding="utf-8")
        (conversion / paths.json).write_text(json.dumps({"title": title, "chunks": [{"text": text}]}), encoding="utf-8")
    state = state_dir(migrated, loaded.id)
    resolved = source.resolve()
    for folder in ("2024", "2025"):
        write_cache(folder_cache(state, folder), [_entry(resolved / f / r) for f, r, _, _ in FILES if f == folder])
    return loaded


@pytest.fixture
def run(user_client: TestClient, project: Project, db: Session, migrated: Settings, tmp_path: Path) -> Iterator[Any]:
    """Encola ``body`` por la API (que fija carpeta y plantilla), lo reclama y devuelve ``(ctx, params)``."""
    contexts: list[JobContext] = []

    def _run(body: dict[str, Any]) -> tuple[JobContext, Any]:
        response = user_client.post(f"/api/v1/projects/{project.id}/runs", json=body)
        assert response.status_code == 202, response.text
        run_id = response.json()["id"]
        assert queue.claim_next(db, "worker-test", ("cpu",)) == run_id
        stored = db.get(Run, run_id)
        assert stored is not None
        db.refresh(stored)
        ctx = JobContext(
            run_id=run_id,
            settings=migrated,
            session_factory=sessionmaker(bind=get_engine(), expire_on_commit=False),
            workdir=tmp_path / run_id,
            created_by=project.created_by,
        )
        contexts.append(ctx)
        return ctx, RUN_PARAMS.validate_python(stored.params)

    yield _run
    for ctx in contexts:
        ctx.stop_cancel_watch()


def _finish(db: Session, ctx: JobContext) -> None:
    db.execute(update(Run).where(Run.id == ctx.run_id).values(status="succeeded"))
    db.commit()


def _logs(db: Session, run_id: str) -> list[str]:
    events = db.scalars(select(RunEvent).where(RunEvent.run_id == run_id, RunEvent.type == "log"))
    return [str(e.data["message"]) for e in events]


DOMAINS = {"operation": "context_build", "catalog": "domains", "domains": ["facturas", "informes"], "build_site": False}


def test_build_classifies_copies_and_projects(run: Any, project: Project, db: Session, migrated: Settings) -> None:
    ctx, params = run(DOMAINS)

    result = operation.run_build(ctx, params, project)

    output = migrated.locations_root / "salidas" / "Proyecto A"
    assert result["output_folder_name"] == "organizado"
    assert result["documents"] + result["unclassified"] == 4 and result["failed"] == 0
    assert (output / "context.json").is_file() and (output / "organizado").is_dir()
    stored = db.get(ProjectContext, project.id)
    assert stored is not None and stored.catalog_kind == "domains" and stored.built_by_run_id == ctx.run_id
    assert {d["slug"] for d in stored.domains} >= {"facturas"}
    docs = list(db.scalars(select(ContextDocument).where(ContextDocument.project_id == project.id)))
    assert {(d.folder, d.path) for d in docs} == {(f, r) for f, r, _, _ in FILES}
    facturas = [d for d in docs if d.domain_slug == "facturas"]
    assert facturas and all(d.organized_path and d.organized_path.startswith("organizado/facturas/") for d in facturas)
    for doc in facturas:
        assert (output / str(doc.organized_path)).is_file()
    # Nada del contenedor en la proyección, el resultado ni los avisos.
    container = str(migrated.locations_root)
    dumped = json.dumps(result) + json.dumps([d.path for d in docs]) + json.dumps(_logs(db, ctx.run_id))
    assert container not in dumped
    assert db.scalar(select(AuditEntry.action).where(AuditEntry.action == "project.context_build"))


def test_rebuild_replaces_the_projection_and_keeps_the_folder(run: Any, project: Project, db: Session) -> None:
    ctx, params = run(DOMAINS | {"output_folder_name": "por-temas"})
    operation.run_build(ctx, params, project)
    _finish(db, ctx)
    first = db.scalar(select(ProjectContext.output_folder_name).where(ProjectContext.project_id == project.id))

    ctx, params = run({"operation": "context_build", "build_site": False})
    result = operation.run_build(ctx, params, project)

    assert first == "por-temas" and result["output_folder_name"] == "por-temas"
    count = db.scalar(
        select(ContextDocument.seq).where(ContextDocument.project_id == project.id).order_by(ContextDocument.seq.desc())
    )
    assert count == 3


def test_build_with_a_template_uses_two_axes(
    run: Any, project: Project, db: Session, user_client: TestClient, admin: Any
) -> None:
    from tests.conftest import ADMIN_PASSWORD, login_as

    admin_client = login_as(user_client, admin.username, ADMIN_PASSWORD)
    assert admin_client.put("/api/v1/taxonomy-templates/obras", json={"markdown": TEMPLATE}).status_code == 201
    ctx, params = run(
        {"operation": "context_build", "catalog": "template", "template_name": "obras", "build_site": False}
    )

    operation.run_build(ctx, params, project)

    stored = db.get(ProjectContext, project.id)
    assert stored is not None and stored.taxonomy_template_name == "obras"
    docs = list(db.scalars(select(ContextDocument).where(ContextDocument.domain_slug.is_not(None))))
    assert docs and all(d.material_type for d in docs)


def test_build_marks_name_collisions(run: Any, project: Project, db: Session) -> None:
    """G30: ``2024/factura.txt`` y ``2025/factura.txt`` van a la misma carpeta de ``organizado/``."""
    ctx, params = run(DOMAINS)

    result = operation.run_build(ctx, params, project)

    collided = list(db.scalars(select(ContextDocument).where(ContextDocument.collision.is_(True))))
    assert result["collisions"] == 2 and {(d.folder, d.path) for d in collided} == {
        ("2024", "factura.txt"),
        ("2025", "factura.txt"),
    }
    assert any("G30" in message for message in _logs(db, ctx.run_id))


def test_build_skips_originals_that_are_gone(run: Any, project: Project, db: Session, migrated: Settings) -> None:
    (migrated.locations_root / "origen" / "2025" / "receta.txt").unlink()
    ctx, params = run(DOMAINS)

    result = operation.run_build(ctx, params, project)

    assert result["missing_originals"] == 1
    assert ("2025", "receta.txt") not in {(d.folder, d.path) for d in db.scalars(select(ContextDocument))}


def test_build_needs_a_writable_destination(run: Any, project: Project, db: Session) -> None:
    ctx, params = run(DOMAINS)
    project.destination_location.access = "ro"
    with pytest.raises(JobFailed) as failed:
        operation.run_build(ctx, params, project)
    assert failed.value.code == "location_read_only"


def test_build_with_the_site(run: Any, project: Project, db: Session, migrated: Settings) -> None:
    ctx, params = run(DOMAINS | {"build_site": True})

    result = operation.run_build(ctx, params, project)

    output = migrated.locations_root / "salidas" / "Proyecto A"
    assert result["site_built"] is True, _logs(db, ctx.run_id)
    assert (output / "site" / "index.html").is_file() and (output / "zensical.toml").is_file()
    stored = db.get(ProjectContext, project.id)
    assert stored is not None and stored.site_built


@pytest.mark.skipif(sys.platform == "win32", reason="enlaces simbólicos")
def test_linked_artifacts_are_never_copied(
    run: Any, project: Project, db: Session, migrated: Settings, tmp_path: Path
) -> None:
    """G27: un original cambiado por un enlace ni se entrega a doc_organize (cuenta como que ya no está); una carpeta
    de imágenes enlazada hace fallar solo ese documento en doc_organize 0.13.0, y el resto se copia."""
    secret = tmp_path / "secreto.txt"
    secret.write_text("facturas secretas", encoding="utf-8")
    original = migrated.locations_root / "origen" / "2025" / "factura.txt"
    original.unlink()
    os.symlink(secret, original)
    images = (
        migrated.locations_root / "salidas" / "Proyecto A" / CONVERSION_DIR / output_paths("2024", "factura.txt").images
    )
    images.parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "img").mkdir()
    (tmp_path / "img" / "secreta.png").write_bytes(b"secreto")
    os.symlink(tmp_path / "img", images)
    ctx, params = run(DOMAINS)

    result = operation.run_build(ctx, params, project)

    assert result["missing_originals"] == 1
    assert result["failed"] == 1 and result["failed_paths"] == ["2024/factura.txt"]
    organized = migrated.locations_root / "salidas" / "Proyecto A" / "organizado"
    assert all(c.read_bytes() not in (b"secreto", b"facturas secretas") for c in organized.rglob("*") if c.is_file())
    failed = db.scalars(select(ContextDocument).where(ContextDocument.failed.is_(True))).one()
    assert failed.organized_path is None
    assert str(tmp_path) not in json.dumps(_logs(db, ctx.run_id))


def test_incomplete_conversions_are_left_out(run: Any, project: Project, migrated: Settings) -> None:
    """Un ``.md`` que falta no tumba la construcción: ese documento no entra (Reorganizer valida todos antes)."""
    conversion = migrated.locations_root / "salidas" / "Proyecto A" / CONVERSION_DIR
    (conversion / output_paths("2024", "obras/informe.txt").markdown).unlink()
    ctx, params = run(DOMAINS)

    result = operation.run_build(ctx, params, project)

    assert result["missing_originals"] == 1 and result["documents"] + result["unclassified"] == 3


@pytest.mark.parametrize("folder", ["..", "/data", "Conversión"])
def test_an_invalid_folder_in_context_json_touches_nothing(
    run: Any, project: Project, db: Session, migrated: Settings, folder: str
) -> None:
    """G32: ``context.json`` se puede cambiar desde el recurso de red; una carpeta no válida no se usa."""
    ctx, params = run(DOMAINS)
    operation.run_build(ctx, params, project)
    _finish(db, ctx)
    output = migrated.locations_root / "salidas" / "Proyecto A"
    data = json.loads((output / "context.json").read_text(encoding="utf-8"))
    (output / "context.json").write_text(json.dumps(data | {"output_folder_name": folder}), encoding="utf-8")
    ctx, params = run(DOMAINS)

    with pytest.raises(JobFailed) as failed:
        operation.run_build(ctx, params, project)

    assert failed.value.code == "context_folder_invalid"
    assert (output / CONVERSION_DIR).is_dir() and (migrated.locations_root / "origen").is_dir()


@pytest.mark.skipif(sys.platform == "win32", reason="enlaces simbólicos")
def test_linked_temporaries_are_removed_before_writing(
    run: Any, project: Project, migrated: Settings, tmp_path: Path
) -> None:
    """G31: doc_organize escribe ``<fichero>.tmp`` sin ``O_NOFOLLOW``; un enlace puesto ahí se quita antes."""
    victim = tmp_path / "config.db"
    victim.write_text("no tocar", encoding="utf-8")
    output = migrated.locations_root / "salidas" / "Proyecto A"
    for name in ("context.tmp", "zensical.toml.tmp"):
        os.symlink(victim, output / name)
    ctx, params = run(DOMAINS)

    operation.run_build(ctx, params, project)

    assert victim.read_text(encoding="utf-8") == "no tocar"
    assert not (output / "context.tmp").is_symlink()


def test_cancel_during_classification_saves_nothing(
    run: Any, project: Project, db: Session, migrated: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx, params = run(DOMAINS)
    calls = iter([False])  # la primera comprobación (antes de reunir documentos) pasa; luego, cancelado
    monkeypatch.setattr(JobContext, "cancelled", property(lambda self: next(calls, True)))

    with pytest.raises(JobCancelled):
        operation.run_build(ctx, params, project)

    assert not (migrated.locations_root / "salidas" / "Proyecto A" / "context.json").exists()
    assert db.get(ProjectContext, project.id) is None


def test_delete_previews_then_removes_only_the_context(
    run: Any, project: Project, db: Session, migrated: Settings
) -> None:
    output = migrated.locations_root / "salidas" / "Proyecto A"
    ctx, params = run(DOMAINS | {"build_site": True})
    operation.run_build(ctx, params, project)
    _finish(db, ctx)

    preview_ctx, preview_params = run({"operation": "context_delete"})
    preview = operation.run_delete(preview_ctx, preview_params, project)
    assert preview["output_folder_name"] == "organizado" and preview["files"] > 0
    assert (output / "context.json").is_file()
    _finish(db, preview_ctx)
    db.execute(update(Run).where(Run.id == preview_ctx.run_id).values(finished_at=Run.created_at, result=preview))
    db.commit()

    real_ctx, real_params = run(
        {
            "operation": "context_delete",
            "dry_run": False,
            "preview_run_id": preview_ctx.run_id,
            "confirm_name": "Proyecto A",
        }
    )
    operation.run_delete(real_ctx, real_params, project)

    for gone in ("context.json", "domains", "organizado", "site", "zensical.toml", ".cache"):
        assert not (output / gone).exists(), gone
    assert (output / CONVERSION_DIR).is_dir()
    assert db.get(ProjectContext, project.id) is None
    assert db.scalar(select(ContextDocument.seq)) is None
    assert db.scalar(select(AuditEntry.action).where(AuditEntry.action == "project.context_delete"))


def test_delete_refuses_a_folder_other_than_the_previewed_one(
    run: Any, project: Project, db: Session, migrated: Settings
) -> None:
    """La vista previa confirmó «organizado»: si context.json pasa a decir otra carpeta, no se borra nada."""
    output = migrated.locations_root / "salidas" / "Proyecto A"
    ctx, params = run(DOMAINS)
    operation.run_build(ctx, params, project)
    _finish(db, ctx)
    preview_ctx, preview_params = run({"operation": "context_delete"})
    preview = operation.run_delete(preview_ctx, preview_params, project)
    _finish(db, preview_ctx)
    db.execute(update(Run).where(Run.id == preview_ctx.run_id).values(finished_at=Run.created_at, result=preview))
    db.commit()
    (output / "otra").mkdir()
    data = json.loads((output / "context.json").read_text(encoding="utf-8"))
    (output / "context.json").write_text(json.dumps(data | {"output_folder_name": "otra"}), encoding="utf-8")
    real_ctx, real_params = run(
        {
            "operation": "context_delete",
            "dry_run": False,
            "preview_run_id": preview_ctx.run_id,
            "confirm_name": "Proyecto A",
        }
    )

    with pytest.raises(JobFailed) as failed:
        operation.run_delete(real_ctx, real_params, project)

    assert failed.value.code == "context_changed"
    assert (output / "otra").is_dir() and (output / "organizado").is_dir()
