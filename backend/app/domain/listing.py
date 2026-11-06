"""Búsqueda y orden comunes de los listados paginados (web 1.2.0).

Cada servicio decide **qué** columnas se pueden buscar y ordenar; aquí solo se aplica de la misma forma en todos:

- ``q``: «contiene» sin distinguir mayúsculas en cualquiera de las columnas de texto, con ``%``, ``_`` y ``\\``
  escapados (un usuario no escribe comodines). SQLite no ignora tildes.
- ``sort``: una clave de la tabla de equivalencias del servicio (la API la valida con un ``Literal``: nunca llega un
  nombre de columna libre). Los ``NULL`` van al final en los dos sentidos.
- Siempre se desempata por la clave primaria, para que la paginación sea estable.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import Select, SQLColumnExpression, func, or_

Order = Literal["asc", "desc"]


@dataclass(frozen=True)
class ListQuery:
    """Búsqueda y orden pedidos para un listado.

    Attributes:
        q: Texto a buscar (``None`` o vacío: sin filtro).
        sort: Clave de orden del servicio (``None``: el orden por defecto del listado).
        order: ``asc`` o ``desc``.
    """

    q: str | None = None
    sort: str | None = None
    order: Order = "asc"


def apply_search[S: Select[Any]](query: S, q: str | None, columns: Sequence[SQLColumnExpression[Any]]) -> S:
    """Filtra ``query`` por ``q`` en alguna de ``columns`` (sin distinguir mayúsculas)."""
    text = (q or "").strip().lower()
    if not text or not columns:
        return query
    return query.where(or_(*(func.lower(column).contains(text, autoescape=True) for column in columns)))


def apply_sort[S: Select[Any]](
    query: S,
    listing: ListQuery,
    columns: Mapping[str, SQLColumnExpression[Any]],
    *,
    default: Sequence[SQLColumnExpression[Any]],
    tiebreak: SQLColumnExpression[Any],
) -> S:
    """Ordena ``query`` por ``listing.sort`` (o por ``default`` si no se pidió) y desempata por ``tiebreak``.

    Raises:
        KeyError: ``listing.sort`` no está en ``columns`` (la API ya lo impide con su ``Literal``).
    """
    if listing.sort is None:
        return query.order_by(*default, tiebreak)
    column = columns[listing.sort]
    ordered = column.desc() if listing.order == "desc" else column.asc()
    return query.order_by(ordered.nulls_last(), tiebreak)
