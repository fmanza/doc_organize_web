"""Tenants y roles (Fase 9)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.api.v1.schemas._common import Permission, RoleName, TenantSlug


class TenantOut(BaseModel):
    """Tenant con sus recuentos (``empty``: se puede borrar)."""

    id: int
    slug: str
    name: str
    created_at: datetime
    users: int
    projects: int
    locations: int
    empty: bool


class TenantPage(BaseModel):
    items: list[TenantOut]
    total: int


class TenantCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: TenantSlug
    name: Annotated[str, Field(min_length=1, max_length=128)]


class TenantUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=1, max_length=128)]


class TenantSwitch(BaseModel):
    """Tenant en el que actuar (``null``: el propio)."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: int | None


class RoleOut(BaseModel):
    id: int
    name: str
    builtin: Literal["admin", "user"] | None
    permissions: list[Permission]
    users: int
    created_at: datetime
    updated_at: datetime


class RoleList(BaseModel):
    items: list[RoleOut]


class RoleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: RoleName
    permissions: list[str] = Field(default_factory=list, max_length=32)


class RoleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: RoleName | None = None
    permissions: list[str] | None = Field(default=None, max_length=32)


class PermissionList(BaseModel):
    """Catálogo de permisos de los roles, en orden."""

    items: list[Permission]
