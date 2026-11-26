"""Tipos y alias compartidos por los esquemas HTTP de la API v1."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from app.domain.identity.passwords import MAX_PASSWORD_LENGTH

Permission = Literal[
    "users.manage", "roles.manage", "audit.read", "templates.manage", "projects.create", "projects.all"
]
TenantSlug = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9-]{1,62}$")]
RoleName = Annotated[str, Field(min_length=1, max_length=64)]
Username = Annotated[str, Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")]
DisplayName = Annotated[str, Field(min_length=1, max_length=128)]
Password = Annotated[SecretStr, Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)]

MAX_PAGE_SIZE = 200


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)
