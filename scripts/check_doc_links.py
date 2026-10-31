"""Comprueba que los enlaces relativos de los Markdown del repositorio apuntan a ficheros existentes.

Provisional hasta la Fase 0, en la que ``zensical build --strict`` valida enlaces y anclas. Solo usa la librería
estándar para que el CI no necesite instalar nada.

Uso: ``python scripts/check_doc_links.py`` desde la raíz del repositorio. Sale con código 1 si hay enlaces rotos.
"""

import re
import sys

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
SKIP_DIRS = {".git", "node_modules", ".venv", "build", "dist", "site"}
EXTERNAL = ("http://", "https://", "mailto:", "#")


def broken_links(md_file: Path) -> list[str]:
    """Devuelve los enlaces relativos de ``md_file`` cuyo destino no existe, sin contar los bloques de código."""
    text = re.sub(r"```.*?```", "", md_file.read_text(encoding="utf-8"), flags=re.DOTALL)
    broken = []
    for target in LINK.findall(text):
        if target.startswith(EXTERNAL):
            continue
        path = target.split("#", 1)[0]
        if path and not (md_file.parent / path).exists():
            broken.append(target)
    return broken


def main() -> int:
    errors = 0
    for md_file in sorted(ROOT.rglob("*.md")):
        if SKIP_DIRS.intersection(md_file.relative_to(ROOT).parts):
            continue
        for target in broken_links(md_file):
            print(f"{md_file.relative_to(ROOT)}: enlace roto -> {target}")
            errors += 1
    print(f"{errors} enlace(s) roto(s)" if errors else "Enlaces internos correctos")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
