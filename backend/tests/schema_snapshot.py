"""Snapshot de la BD que deja la cadena de migraciones en ``0033``: DDL de ``sqlite_master`` y filas semilla.

Es la referencia del squash de Alembic de la 3.0 (``docs/plan/VERSION_3.0.md``): la línea base tiene que dejar
exactamente esta BD. Se regenera solo si cambia a propósito una migración hasta ``0033``::

    uv run --frozen python -m tests.schema_snapshot
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

SNAPSHOT = Path(__file__).parent / "fixtures" / "schema_0033.sql"
REVISION = "0033"
#: Columnas que cambian en cada ejecución: no forman parte del snapshot.
VOLATILE = frozenset({"created_at", "updated_at"})


_TABLE_CONSTRAINT = ("CONSTRAINT ", "PRIMARY KEY", "UNIQUE", "FOREIGN KEY", "CHECK")


def _split_top_level(body: str) -> list[str]:
    """Parte la lista de un ``CREATE TABLE`` por las comas que no están entre paréntesis ni comillas."""
    items: list[str] = []
    depth, quote, start = 0, "", 0
    for index, char in enumerate(body):
        if quote:
            if char == quote:
                quote = ""
        elif char in "'\"":
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "," and depth == 0:
            items.append(body[start:index].strip())
            start = index + 1
    items.append(body[start:].strip())
    return items


def _normalize_table(sql: str) -> str:
    """Columnas en su orden y restricciones de tabla ordenadas.

    Las migraciones *batch* de Alembic recrean las tablas y emiten sus restricciones en un orden que depende del
    ``PYTHONHASHSEED``: el texto literal no es estable entre ejecuciones, el conjunto sí.
    """
    head, _, rest = sql.partition("(")
    body, _, tail = rest.rpartition(")")
    items = _split_top_level(body)
    columns = [item for item in items if not item.upper().startswith(_TABLE_CONSTRAINT)]
    constraints = sorted(item for item in items if item.upper().startswith(_TABLE_CONSTRAINT))
    inner = ",\n\t".join(columns + constraints)
    return f"{head.strip()} (\n\t{inner}\n){tail}"


def dump(database: Path) -> str:
    """DDL ordenado por tipo y nombre, y filas de las tablas con datos, sin columnas volátiles."""
    with closing(sqlite3.connect(database)) as connection:
        lines: list[str] = []
        ddl = connection.execute(
            "SELECT type, name, sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' "
            "ORDER BY type, name"
        )
        for kind, name, sql in ddl:
            text = _normalize_table(sql) if kind == "table" else sql
            lines.append(f"-- {kind} {name}\n{text};")
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        for table in tables:
            columns = [row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')]
            kept = [column for column in columns if column not in VOLATILE]
            select = ", ".join(f'"{column}"' for column in kept)
            rows = connection.execute(f'SELECT {select} FROM "{table}" ORDER BY 1').fetchall()  # noqa: S608
            for row in rows:
                values = ", ".join(repr(value) for value in row)
                lines.append(f"-- row {table} ({', '.join(kept)})\n({values})")
    return "\n\n".join(lines) + "\n"


def main() -> None:
    from alembic import command

    from tests.conftest import alembic_config

    with tempfile.TemporaryDirectory() as data_dir:
        os.environ["DOW_ENVIRONMENT"] = "test"
        os.environ["DOW_DATA_DIR"] = data_dir
        command.upgrade(alembic_config(), REVISION)
        from app.db.session import get_engine

        get_engine().dispose()
        SNAPSHOT.parent.mkdir(exist_ok=True)
        SNAPSHOT.write_text(dump(Path(data_dir) / "config.db"), encoding="utf-8", newline="\n")
    print(f"escrito {SNAPSHOT}")


if __name__ == "__main__":
    main()
