"""Autenticación, CSRF y preferencias del propio usuario."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.api.v1.schemas._common import Password, Permission, _Out


class CsrfToken(BaseModel):
    """Token CSRF para la cabecera ``X-CSRF-Token``."""

    csrf_token: str


class LoginRequest(BaseModel):
    """Credenciales de inicio de sesión."""

    username: Annotated[str, Field(min_length=1, max_length=64)]
    password: Password


ColorScheme = Literal["auto", "light", "dark"]
"""Tema de la interfaz: ``auto`` sigue al sistema operativo."""


Language = Literal["es", "en"]
"""Idioma de la interfaz (2.6)."""


class Preferences(BaseModel):
    """Preferencias del propio usuario: tema (2.3) e idioma (2.6). Se guarda lo que llegue; al menos una."""

    model_config = ConfigDict(extra="forbid")

    color_scheme: ColorScheme | None = None
    language: Language | None = None

    @model_validator(mode="after")
    def _at_least_one(self) -> Preferences:
        if self.color_scheme is None and self.language is None:
            raise ValueError("Indica al menos una preferencia")
        return self


class PasswordChange(BaseModel):
    """Cambio de la propia contraseña."""

    current_password: Password
    new_password: Password


class TenantRef(_Out):
    id: int
    slug: str
    name: str


class RoleRef(_Out):
    id: int
    name: str
    builtin: Literal["admin", "user"] | None


class Me(BaseModel):
    """Usuario de la sesión actual: su tenant, el tenant en el que actúa (distinto solo para un admin de instancia que
    lo cambió con el selector), su rol y sus permisos en el tenant activo (Fase 9)."""

    id: int
    username: str
    display_name: str
    tenant: TenantRef
    acting_tenant: TenantRef
    is_instance_admin: bool
    role: RoleRef
    permissions: list[Permission]
    color_scheme: ColorScheme
    language: Language
