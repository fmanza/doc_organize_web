"""Frescura del contexto (W4, doc_organize 2.0 F4): tras construir, al día; si la caché cambia (otra huella, un
original nuevo convertido o uno que ya no está), el contexto queda desactualizado, con rutas relativas y sin leer
originales. Datos sintéticos."""

from __future__ import annotations

import time
from typing import Any

import pytest
from doc_organize import CacheEntry
from doc_organize.core.models import ConversionStatus, DocumentStatus
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Project, ProjectContext
from app.domain.projects.service import state_dir
from app.domain.scan.state import folder_cache
from app.jobs.operations import context as operation
from tests.api.test_documents import write_cache
from tests.jobs.test_context_operation import DOMAINS, FILES


def _entry(path: Any, sha: str, status: DocumentStatus = DocumentStatus.NEW) -> CacheEntry:
    return CacheEntry(
        file_path=str(path),
        sha256_hash=sha,
        timestamp=time.time(),
        status=status,
        conversion_status=ConversionStatus.SUCCESS,
    )


@pytest.mark.posix_paths
def test_freshness_after_build_and_after_the_cache_changes(
    run: Any, project: Project, db: Session, migrated: Settings, user_client: TestClient
) -> None:
    ctx, params = run(DOMAINS)
    operation.run_build(ctx, params, project)

    stored = db.get(ProjectContext, project.id)
    assert stored is not None and stored.freshness is not None
    assert stored.freshness["up_to_date"] is True and stored.freshness["changed"] == 0
    assert stored.freshness["unknown"] == 0  # 2.0: el contexto guarda la huella de cada original

    # 2025: la receta cambió, la factura se borró (la caché la marca) y hay un original nuevo convertido.
    source = (migrated.locations_root / "origen").resolve()
    write_cache(
        folder_cache(state_dir(migrated, project.id), "2025"),
        [
            _entry(source / "2025" / "receta.txt", "1" * 64),
            _entry(source / "2025" / "factura.txt", "0" * 64, DocumentStatus.DELETED),
            _entry(source / "2025" / "nuevo.txt", "2" * 64),
        ],
    )
    freshness = operation.refresh_freshness(ctx, project)

    assert freshness is not None and freshness["up_to_date"] is False
    assert (freshness["changed"], freshness["added"], freshness["removed"]) == (1, 1, 1)
    assert freshness["examples"]["changed"] == ["2025/receta.txt"]
    assert freshness["examples"]["added"] == ["2025/nuevo.txt"]
    assert freshness["examples"]["removed"] == ["2025/factura.txt"]
    assert str(migrated.locations_root) not in str(freshness)
    body = user_client.get(f"/api/v1/projects/{project.id}/context").json()
    assert body["freshness"]["up_to_date"] is False and body["freshness"]["removed"] == 1
    assert {f for f, *_ in FILES} == {"2024", "2025"}


def test_freshness_without_context_does_nothing(run: Any, project: Project) -> None:
    ctx, _ = run(DOMAINS)
    assert operation.refresh_freshness(ctx, project) is None
