"""Puerta de versión de las migraciones (ADR-018): desde la 3.0 la cadena empieza en la línea base ``0033``."""

from __future__ import annotations

from alembic.script import ScriptDirectory
from alembic.util import CommandError
from sqlalchemy import Connection, inspect


class UnsupportedRevisionError(RuntimeError):
    """La ``config.db`` está en una revisión que ya no existe: viene de una web anterior a la 2.7."""


def check_revision_is_known(connection: Connection, script: ScriptDirectory) -> None:
    """Solo se actualiza desde la 2.7.x o la 2.8.x, que están en ``0033``; una BD vacía o nueva pasa.

    Raises:
        UnsupportedRevisionError: La BD tiene una revisión que no está en ``alembic/versions``. El mensaje no incluye la
            ruta de la BD.
    """
    if "alembic_version" not in inspect(connection).get_table_names():
        return
    current = connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar()
    if current is None:
        return
    try:
        known = script.get_revision(str(current)) is not None
    except CommandError:
        known = False
    if not known:
        raise UnsupportedRevisionError(
            f"La base de datos está en la revisión {current}, de una versión de la web anterior a la 2.7. "
            "La 3.0 solo actualiza desde la 2.7.x o la 2.8.x: instala la 2.8.x, arráncala una vez para que migre y "
            "vuelve a instalar la 3.0."
        )
