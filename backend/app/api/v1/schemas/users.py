"""Usuarios: alta, edición, bloqueo y borrado."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.api.v1.schemas._common import DisplayName, Password, Username, _Out
from app.api.v1.schemas.auth import RoleRef

#: Estado por el que se filtra la lista de usuarios (2.7).
UserStatus = Literal["active", "inactive", "locked"]


class UserOut(_Out):
    """Usuario visto por quien gestiona usuarios."""

    id: int
    username: str
    display_name: str
    tenant_id: int
    role: RoleRef
    is_instance_admin: bool
    is_active: bool
    locked_until: datetime | None
    failed_attempts: int
    password_changed_at: datetime
    created_at: datetime
    updated_at: datetime


class UserCreate(BaseModel):
    """Alta de usuario."""

    username: Username
    display_name: DisplayName
    password: Password
    role_id: int | None = Field(default=None, description="Rol del tenant; sin él, «Usuario»")
    is_instance_admin: bool = Field(default=False, description="Solo lo da un administrador de la instancia")
    tenant_id: int | None = Field(default=None, description="Solo el admin de instancia; sin él, el tenant activo")


class UserUpdate(BaseModel):
    """Edición parcial de usuario; ``password`` restablece la contraseña y cierra sus sesiones; ``unlock`` quita el
    bloqueo por intentos fallidos."""

    display_name: DisplayName | None = None
    role_id: int | None = None
    is_instance_admin: bool | None = None
    tenant_id: int | None = Field(
        default=None, description="Mover a otro tenant (solo admin de instancia): pierde sus proyectos y sesiones"
    )
    is_active: bool | None = None
    password: Password | None = None
    unlock: bool = False
    reason: str | None = Field(
        default=None,
        max_length=200,
        description="Motivo de desactivar (bloquear) o reactivar: solo va a la auditoría (2.7)",
    )


class UserPage(BaseModel):
    """Página de usuarios."""

    items: list[UserOut]
    total: int
    active_instance_admins: int | None = Field(
        default=None,
        description="Admins de instancia activos (siempre al menos uno, 2.7); solo para un admin de instancia",
    )


#: Motivo por el que un usuario no se puede borrar (ADR-016).
DeletionReason = Literal["self", "last_instance_admin", "last_manager", "sole_owner", "active_runs"]


class DeletionProjectRef(BaseModel):
    """Proyecto citado en la comprobación de borrado: solo id, nombre y rol del usuario en él."""

    id: int
    name: str
    role: str


class UserDeletionCheck(BaseModel):
    """Qué impide borrar a un usuario y qué se borraría con él (ADR-016). Es también el cuerpo del ``409``."""

    can_delete: bool
    reasons: list[DeletionReason]
    sole_owner_projects: list[DeletionProjectRef] = Field(description="Proyectos de los que es el único propietario")
    memberships: list[DeletionProjectRef] = Field(description="Proyectos de los que sale al borrarlo")
    active_runs: int = Field(description="Runs suyos en cola o en marcha")
    sessions: int = Field(description="Sesiones abiertas que se cierran")
