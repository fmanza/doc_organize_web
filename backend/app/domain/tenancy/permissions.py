"""Catálogo fijo de permisos de los roles de un tenant (Fase 9, ADR-013).

Son permisos de **administración dentro de un tenant**. El acceso a cada proyecto sigue siendo por miembros
(``owner``/``editor``/``viewer``), y lo que es del servidor (tenants, ubicaciones, ajustes, IA, workers) es del admin de
instancia (``users.is_instance_admin``).
"""

from __future__ import annotations

from typing import Final, Literal

Permission = Literal[
    "users.manage",
    "roles.manage",
    "audit.read",
    "templates.manage",
    "projects.create",
    "projects.all",
]

#: Orden en que se muestran.
PERMISSIONS: Final[tuple[Permission, ...]] = (
    "users.manage",
    "roles.manage",
    "audit.read",
    "templates.manage",
    "projects.create",
    "projects.all",
)

BuiltinRole = Literal["admin", "user"]

#: Roles base de cada tenant: no se borran ni cambian sus permisos.
BUILTIN_ROLES: Final[dict[BuiltinRole, tuple[str, frozenset[Permission]]]] = {
    "admin": ("Administrador", frozenset(PERMISSIONS)),
    "user": ("Usuario", frozenset({"projects.create"})),
}


def normalize(permissions: list[str] | tuple[str, ...] | frozenset[str]) -> list[Permission]:
    """Permisos válidos de ``permissions`` en el orden del catálogo (los desconocidos se descartan)."""
    wanted = set(permissions)
    return [p for p in PERMISSIONS if p in wanted]


def unknown(permissions: list[str]) -> list[str]:
    """Los de ``permissions`` que no están en el catálogo."""
    return sorted(set(permissions) - set(PERMISSIONS))
