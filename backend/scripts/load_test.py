"""Prueba de carga con el objetivo de diseño (Fase 10, WB-10.6): 100 000 documentos y 10 000 grupos de duplicados.

Monta una instancia **en proceso** sobre una carpeta temporal (``config.db`` migrada, un admin, dos ubicaciones y un
proyecto) y la llena de datos **sintéticos** sin convertir nada: las entradas de la caché de doc_organize (con su
``CacheManager``), un ``dedup_preview`` con sus grupos y un historial de runs. Después mide la API con ``TestClient``
(la aplicación y SQLite, sin red ni proxy): páginas del principio, del medio y del final de cada listado, y búsquedas.

    uv run --frozen python scripts/load_test.py                       # 100 000 / 10 000 / 5 000
    uv run --frozen python scripts/load_test.py --documents 20000 --report ../build/logs/carga.json

Sale con 1 si el p95 de algún listado pasa de ``--p95-ms`` (500 por defecto).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
import statistics
import sys
import tempfile
import time
import uuid
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

#: Instancia temporal y desechable: la contraseña del admin es aleatoria en cada ejecución.
ADMIN_PASSWORD = secrets.token_urlsafe(16)


def _environment(root: Path) -> None:
    os.environ["DOW_ENVIRONMENT"] = "test"
    for name in ("data", "workspace", "static"):
        os.environ[f"DOW_{name.upper()}_DIR"] = str(root / name)
    os.environ["DOW_LOCATIONS_ROOT"] = str(root / "mnt")
    os.environ["DOW_RATE_LIMIT_LOGIN"] = "10000"
    os.environ["DOW_RATE_LIMIT_WRITE"] = "100000"
    os.environ["DOW_LOG_LEVEL"] = "WARNING"


def _migrate() -> None:
    from alembic import command
    from alembic.config import Config

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(config, "head")


def _fill_cache(cache_db: Path, folder: Path, documents: int) -> None:
    from doc_organize import CacheEntry, CacheManager, ConversionStatus, DocumentStatus

    statuses = [ConversionStatus.SUCCESS] * 18 + [ConversionStatus.ERROR, ConversionStatus.PENDING]

    async def _save() -> None:
        cache_db.parent.mkdir(parents=True, exist_ok=True)
        async with CacheManager(cache_db) as cache:
            batch: list[CacheEntry] = []
            for index in range(documents):
                status = statuses[index % len(statuses)]
                batch.append(
                    CacheEntry(
                        file_path=f"{folder}/expedientes/{index % 500:03d}/documento-{index:06d}.pdf",
                        sha256_hash=f"{index:064x}",
                        timestamp=1_700_000_000.0 + index,
                        status=DocumentStatus.UNCHANGED,
                        conversion_status=status,
                        error_message="Documento dañado (sintético)" if status == ConversionStatus.ERROR else None,
                    )
                )
                if len(batch) == 5_000:
                    await cache.save_entries(batch)
                    batch = []
            await cache.save_entries(batch)

    asyncio.run(_save())


def _fill_database(project_id: int, admin_id: int, groups: int, runs: int) -> str:
    from sqlalchemy.orm import sessionmaker

    from app.db.models import DuplicateGroupRow, Run, utcnow
    from app.db.session import get_engine

    preview_id = str(uuid.uuid4())
    now = utcnow()
    with sessionmaker(bind=get_engine())() as db:
        db.add_all(
            Run(
                id=str(uuid.uuid4()),
                project_id=project_id,
                operation="noop",
                status="succeeded",
                params={"operation": "noop"},
                created_by=admin_id,
                created_at=now - timedelta(minutes=index),
                finished_at=now - timedelta(minutes=index),
            )
            for index in range(runs)
        )
        db.add(
            Run(
                id=preview_id,
                project_id=project_id,
                operation="dedup_preview",
                status="succeeded",
                params={"operation": "dedup_preview"},
                result={"groups": groups},
                created_by=admin_id,
                created_at=now,
                finished_at=now,
            )
        )
        db.flush()
        for start in range(0, groups, 2_000):
            db.add_all(
                DuplicateGroupRow(
                    run_id=preview_id,
                    group_id=str(uuid.uuid4()),
                    reason="exact_duplicate",
                    position=index,
                    member_count=3,
                    members=[
                        {  # mismo formato que guarda el job dedup_preview (``_member``)
                            "folder": "2024",
                            "path": f"expedientes/{index % 500:03d}/copia-{index:06d}-{copy}.pdf",
                            "size_bytes": 1024,
                            "modified_time": 1_700_000_000.0 + index,
                            "sha256": f"{index:064x}",
                            "canonical": copy == 0,
                        }
                        for copy in range(3)
                    ],
                )
                for index in range(start, min(groups, start + 2_000))
            )
            db.commit()
        db.commit()
    return preview_id


def _measure(call: Callable[[], Any], repeat: int) -> dict[str, float]:
    samples: list[float] = []
    for _ in range(repeat):
        start = time.perf_counter()
        response = call()
        samples.append((time.perf_counter() - start) * 1000)
        if response.status_code != 200:
            raise RuntimeError(f"{response.request.url} → {response.status_code}: {response.text[:200]}")
    samples.sort()
    return {
        "p50_ms": round(statistics.median(samples), 1),
        "p95_ms": round(samples[max(0, int(len(samples) * 0.95) - 1)], 1),
        "max_ms": round(samples[-1], 1),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prueba de carga de los listados paginados")
    parser.add_argument("--documents", type=int, default=100_000)
    parser.add_argument("--groups", type=int, default=10_000)
    parser.add_argument("--runs", type=int, default=5_000)
    parser.add_argument("--repeat", type=int, default=20, help="peticiones por caso")
    parser.add_argument("--p95-ms", type=float, default=500.0)
    parser.add_argument("--report", type=Path, help="informe JSON (p. ej. ../build/logs/carga.json)")
    args = parser.parse_args(argv)

    with tempfile.TemporaryDirectory(prefix="dow-carga-") as tmp:
        root = Path(tmp)
        _environment(root)
        for folder in ("mnt/origen/2024", "mnt/salidas"):
            (root / folder).mkdir(parents=True)

        from fastapi.testclient import TestClient
        from sqlalchemy.orm import sessionmaker

        from app.core.config import get_settings
        from app.db.models import DEFAULT_TENANT_ID
        from app.db.session import get_engine
        from app.domain.identity.audit import CLI_CONTEXT
        from app.domain.identity.users import create_user
        from app.domain.locations.service import create_location
        from app.domain.scan.state import folder_cache
        from app.domain.tenancy.roles import builtin_role
        from app.main import create_app

        _migrate()
        settings = get_settings()
        with sessionmaker(bind=get_engine(), expire_on_commit=False)() as db:
            admin = create_user(
                db,
                username="carga",
                display_name="Carga",
                password=ADMIN_PASSWORD,
                settings=settings,
                ctx=CLI_CONTEXT,
                actor=None,
                tenant_id=DEFAULT_TENANT_ID,
                role_id=builtin_role(db, DEFAULT_TENANT_ID, "admin").id,
                is_instance_admin=True,
            )
            common: dict[str, Any] = {
                "display_path": None,
                "kind": "local",
                "settings": settings,
                "actor": admin,
                "ctx": CLI_CONTEXT,
                "tenant_id": DEFAULT_TENANT_ID,
            }
            source = create_location(db, name="Origen", path="origen", usage="source", access="ro", **common)
            destination = create_location(
                db, name="Salidas", path="salidas", usage="destination", access="rw", **common
            )

        with TestClient(create_app(settings), base_url="https://testserver") as client:
            csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
            client.post(
                "/api/v1/auth/login",
                json={"username": "carga", "password": ADMIN_PASSWORD},
                headers={"X-CSRF-Token": csrf},
            ).raise_for_status()
            client.headers["X-CSRF-Token"] = client.cookies[settings.csrf_cookie]
            project = client.post(
                "/api/v1/projects",
                json={
                    "name": "Carga",
                    "source_location_id": source.id,
                    "source_subpaths": ["2024"],
                    "destination_location_id": destination.id,
                    "destination_parent": "",
                    "new_folder": "Carga",
                },
            )
            project.raise_for_status()
            project_id = int(project.json()["id"])

            started = time.perf_counter()
            folder = (settings.locations_root / "origen" / "2024").resolve()
            _fill_cache(folder_cache(settings.data_dir / "projects" / str(project_id), "2024"), folder, args.documents)
            preview_id = _fill_database(project_id, admin.id, args.groups, args.runs)
            print(f"Datos sintéticos listos en {time.perf_counter() - started:.1f} s")

            documents = f"/api/v1/projects/{project_id}/documents"
            groups = f"/api/v1/runs/{preview_id}/duplicate-groups"
            last_doc = max(0, args.documents - 50)
            last_group = max(0, args.groups - 10)
            cases: dict[str, Callable[[], Any]] = {
                "documentos, primera página": lambda: client.get(documents, params={"limit": 50}),
                "documentos, página del medio": lambda: client.get(
                    documents, params={"limit": 50, "offset": args.documents // 2}
                ),
                "documentos, última página": lambda: client.get(documents, params={"limit": 50, "offset": last_doc}),
                "documentos, búsqueda": lambda: client.get(documents, params={"limit": 50, "search": "documento-0999"}),
                "documentos, con error": lambda: client.get(
                    documents, params={"limit": 50, "conversion_status": "error", "offset": 1000}
                ),
                "duplicados, primera página": lambda: client.get(groups, params={"limit": 10}),
                "duplicados, última página": lambda: client.get(groups, params={"limit": 10, "offset": last_group}),
                "ejecuciones, primera página": lambda: client.get("/api/v1/runs", params={"limit": 25}),
                "ejecuciones, última página": lambda: client.get(
                    "/api/v1/runs", params={"limit": 25, "offset": max(0, args.runs - 25)}
                ),
            }
            first = client.get(documents, params={"limit": 1}).json()
            if first["total"] != args.documents:
                print(f"ERROR: la API ve {first['total']} documentos, no {args.documents}", file=sys.stderr)
                return 1
            results = {name: _measure(call, args.repeat) for name, call in cases.items()}

    slow = {name: r for name, r in results.items() if r["p95_ms"] > args.p95_ms}
    width = max(len(name) for name in results)
    for name, r in results.items():
        mark = "  ← lento" if name in slow else ""
        print(
            f"{name:<{width}}  p50 {r['p50_ms']:>7.1f} ms  p95 {r['p95_ms']:>7.1f} ms  máx {r['max_ms']:>7.1f} ms{mark}"
        )
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(
                {
                    "documents": args.documents,
                    "groups": args.groups,
                    "runs": args.runs,
                    "repeat": args.repeat,
                    "p95_limit_ms": args.p95_ms,
                    "results": results,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    print("Todos los listados por debajo del límite." if not slow else f"{len(slow)} listados por encima del límite.")
    return 1 if slow else 0


if __name__ == "__main__":
    raise SystemExit(main())
