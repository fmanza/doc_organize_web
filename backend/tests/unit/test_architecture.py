"""Reglas de arquitectura comprobadas sobre el código (ADR-006, ``.ai/architecture.md``)."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[2] / "app"
ANTI_CORRUPTION = APP_DIR / "integrations" / "doc_organize"


def _imported_roots(path: Path) -> set[str]:
    """Paquetes de primer nivel importados de forma absoluta por ``path``."""
    roots: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_only_anti_corruption_layer_imports_doc_organize() -> None:
    offenders = [
        str(p.relative_to(APP_DIR))
        for p in APP_DIR.rglob("*.py")
        if not p.is_relative_to(ANTI_CORRUPTION) and {"doc_organize", "docling"} & _imported_roots(p)
    ]

    assert offenders == [], f"Solo app/integrations/doc_organize puede importar doc_organize: {offenders}"


def test_domain_does_not_import_web_framework() -> None:
    offenders = [
        str(p.relative_to(APP_DIR))
        for p in (APP_DIR / "domain").rglob("*.py")
        if {"fastapi", "starlette"} & _imported_roots(p)
    ]

    assert offenders == [], f"app/domain no puede importar FastAPI ni Starlette: {offenders}"


def test_anti_corruption_layer_does_not_import_api_or_domain() -> None:
    offenders = []
    for path in ANTI_CORRUPTION.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        modules = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        if any(m.startswith(("app.api", "app.domain")) for m in modules):
            offenders.append(str(path.relative_to(APP_DIR)))

    assert offenders == []


def test_api_and_worker_parent_do_not_load_doc_organize() -> None:
    """G15: la API y el proceso padre del worker no cargan doc_organize; solo el subproceso del job (y el de
    capacidades) lo importan, dentro de las funciones de la capa anticorrupción."""
    code = "import sys, app.main, app.jobs.worker; print(sorted(m for m in sys.modules if m.split('.')[0] in {'doc_organize', 'docling', 'torch'}))"
    completed = subprocess.run(  # noqa: S603 - intérprete actual con código fijo
        [sys.executable, "-c", code], cwd=APP_DIR.parent, capture_output=True, text=True, check=True
    )

    assert completed.stdout.strip() == "[]"
