"""Prueba de ida y vuelta de las migraciones sobre una **copia** de ``config.db`` (plan único 2.0, W2).

Copia la base de datos que se le da a un directorio temporal (nunca abre el original para escribir), la sube a
``head`` con Alembic, comprueba que la aplicación la puede leer, la baja a la revisión de partida y compara tabla a
tabla las filas de antes y de después. Solo imprime nombres de tabla, recuentos y huellas: ningún valor (la copia puede
llevar nombres de documentos, rutas y credenciales cifradas).

Uso, con la web parada o sobre una copia ya hecha con ``python -m app.cli backup``::

    uv run python scripts/migration_roundtrip.py /ruta/a/una/copia/config.db

Sale con 0 si la ida y vuelta deja las mismas filas en todas las tablas de la revisión de partida.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _snapshot(path: Path) -> dict[str, tuple[int, str]]:
    """Tabla → (filas, huella de sus filas ordenadas), de las tablas de la aplicación."""
    with closing(sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)) as conn:
        tables = [
            name
            for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")
            if not name.startswith("sqlite_") and name != "alembic_version"
        ]
        result: dict[str, tuple[int, str]] = {}
        for table in tables:
            columns = sorted(row[1] for row in conn.execute(f'PRAGMA table_info("{table}")'))
            select = ", ".join(f'"{column}"' for column in columns)
            rows = sorted(repr(row) for row in conn.execute(f'SELECT {select} FROM "{table}"'))  # noqa: S608
            digest = hashlib.sha256("\n".join([*columns, *rows]).encode("utf-8")).hexdigest()
            result[table] = (len(rows), digest)
        return result


def _revision(path: Path) -> str | None:
    with closing(sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)) as conn:
        row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
        return str(row[0]) if row else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("database", type=Path, help="copia de config.db (no se modifica)")
    args = parser.parse_args(argv)
    source: Path = args.database.resolve()
    if not source.is_file():
        parser.error(f"no existe {source}")

    # Windows: el engine de la aplicación puede retener el fichero un momento; el directorio se borra igualmente al salir.
    with tempfile.TemporaryDirectory(prefix="dow-roundtrip-", ignore_cleanup_errors=True) as workdir:
        data_dir = Path(workdir)
        copy = data_dir / "config.db"
        with (
            closing(sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)) as src,
            closing(sqlite3.connect(copy)) as dst,
        ):
            src.backup(dst)  # copia coherente aunque el original esté en modo WAL
        start = _revision(copy)
        if start is None:
            print("La copia no tiene revisión de Alembic.")
            return 2
        before = _snapshot(copy)

        os.environ["DOW_DATA_DIR"] = str(data_dir)
        os.environ.setdefault("DOW_ENVIRONMENT", "development")
        sys.path.insert(0, str(BACKEND_DIR))
        from alembic import command
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        from app.core.config import get_settings

        get_settings.cache_clear()
        config = Config(str(BACKEND_DIR / "alembic.ini"))
        head = ScriptDirectory.from_config(config).get_current_head()
        print(f"Revisión de partida: {start}; head: {head}")
        command.upgrade(config, "head")
        after_upgrade = _snapshot(copy)
        print("Tras subir:")
        for table, (count, _) in sorted(after_upgrade.items()):
            mark = "" if table in before else "  (nueva)"
            print(f"  {table}: {count} filas{mark}")
        _check_models(copy)
        command.downgrade(config, start)
        after = _snapshot(copy)
        from app.db.session import get_engine

        get_engine().dispose()

    differences = [table for table in before if before[table] != after.get(table)]
    extra = sorted(set(after) - set(before))
    print(f"Tras bajar a {start}: {len(before)} tablas comparadas, {len(differences)} distintas, sobran {extra}")
    for table in differences:
        print(f"  DISTINTA: {table} ({before[table][0]} filas antes, {after.get(table, (0, ''))[0]} después)")
    return 0 if not differences and not extra else 1


def _check_models(copy: Path) -> None:
    """La aplicación lee la base de datos subida: un ``SELECT`` de cada modelo (sin imprimir valores)."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.db.base import Base

    engine = create_engine(f"sqlite:///{copy.as_posix()}")
    with Session(engine) as db:
        for mapper in Base.registry.mappers:
            db.execute(select(mapper.class_).limit(5)).all()
    engine.dispose()
    print("Modelos de la aplicación leídos sin errores.")


if __name__ == "__main__":
    raise SystemExit(main())
