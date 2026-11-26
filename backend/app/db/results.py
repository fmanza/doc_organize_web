"""Ayudas tipadas sobre los resultados de SQLAlchemy."""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy import CursorResult, Result


def affected_rows(result: Result[Any]) -> int:
    """Filas que tocó un ``UPDATE`` o ``DELETE``.

    ``Session.execute`` está tipado como ``Result``, pero una sentencia DML devuelve un ``CursorResult``, el único que
    tiene ``rowcount``.
    """
    return int(cast(CursorResult[Any], result).rowcount or 0)
