"""Parámetros comunes de búsqueda y orden de los listados (web 1.2.0).

``sort`` es un ``Literal`` por listado: un valor que no está en él da 422 y nunca llega al dominio como nombre de
columna. Cada clave tiene su columna en el servicio (``tests/api/test_listing.py`` las recorre todas).
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import Query

from app.api.v1.schemas import MAX_FOLDER_PAGE, MAX_PAGE_SIZE
from app.domain.listing import ListQuery, Order

SearchQuery = Annotated[
    str | None, Query(max_length=100, description="Texto a buscar: contiene, sin distinguir mayúsculas")
]
OrderQuery = Annotated[Order, Query(description="Sentido del orden")]
# Paginación ``limit``/``offset`` acotada; el valor por defecto lo pone cada endpoint.
LimitQuery = Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)]
FolderLimitQuery = Annotated[int, Query(ge=1, le=MAX_FOLDER_PAGE)]
OffsetQuery = Annotated[int, Query(ge=0)]

UserSort = Literal["username", "display_name", "role", "status", "created_at"]
TenantSort = Literal["name", "slug", "users", "projects", "locations"]
LocationSort = Literal["name", "usage", "access", "status", "probed_at"]
ProjectSort = Literal["name", "source", "destination", "last_run"]
RunSort = Literal["operation", "project", "status", "created_at", "duration", "created_by"]
SessionSort = Literal["username", "ip", "user_agent", "created_at", "last_seen_at", "expires_at"]
AuditSort = Literal["ts", "action", "outcome", "actor", "target", "ip"]
ScanErrorSort = Literal["path", "message", "retry_count"]
GroupSort = Literal["position", "reason", "member_count"]
ContextDocumentSort = Literal["title", "path", "document_type", "organized_path"]
#: Documentos de la caché (web 1.3.0): los ordena doc_organize 1.2.0 (G40).
DocumentSort = Literal[
    "path",
    "updated_at",
    "conversion_status",
    "status",
    "error_retry_count",
    # doc_organize 1.6.0 (G43); ``owner_name`` solo para quien ve la columna (owners y admins).
    "mime_type",
    "created_at",
    "owner_name",
]


def listing(q: str | None, sort: str | None, order: Order) -> ListQuery:
    """El ``ListQuery`` de un endpoint a partir de sus parámetros."""
    return ListQuery(q=q, sort=sort, order=order)
