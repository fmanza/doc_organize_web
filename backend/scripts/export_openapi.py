"""Escribe el esquema OpenAPI de la API en ``openapi/openapi.json`` (contrato del cliente del frontend).

Uso (desde ``backend/``)::

    uv run python scripts/export_openapi.py            # escribe
    uv run python scripts/export_openapi.py --check    # falla si el fichero no coincide (CI)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402

TARGET = Path(__file__).resolve().parents[2] / "openapi" / "openapi.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="no escribe; sale con 1 si hay diferencias")
    args = parser.parse_args()

    schema = create_app(Settings(environment="test", static_dir=Path("__no_static__"))).openapi()
    content = json.dumps(schema, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if args.check:
        current = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""
        if current != content:
            print(f"{TARGET} desactualizado: ejecuta scripts/export_openapi.py", file=sys.stderr)
            return 1
        return 0
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(content, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
