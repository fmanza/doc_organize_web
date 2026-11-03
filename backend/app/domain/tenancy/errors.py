"""Errores de tenants, roles y permisos (Fase 9), con ``code`` estable para el cliente."""

from __future__ import annotations

from app.core.errors import AppError


class TenantNotFoundError(AppError):
    status = 404
    title = "Tenant no encontrado"
    code = "tenant_not_found"


class TenantSlugTakenError(AppError):
    status = 409
    title = "Identificador de tenant en uso"
    code = "tenant_slug_taken"


class TenantNotEmptyError(AppError):
    """El tenant tiene usuarios, proyectos, ubicaciones o plantillas (decisión E3: no hay borrado en cascada)."""

    status = 409
    title = "El tenant no está vacío"
    code = "tenant_not_empty"


class TenantProtectedError(AppError):
    """El tenant ``default`` no se borra."""

    status = 409
    title = "Tenant protegido"
    code = "tenant_protected"


class RoleNotFoundError(AppError):
    status = 404
    title = "Rol no encontrado"
    code = "role_not_found"


class RoleNameTakenError(AppError):
    status = 409
    title = "Ya hay un rol con ese nombre"
    code = "role_name_taken"


class RoleBuiltinError(AppError):
    """Los roles base no se borran ni cambian de permisos."""

    status = 409
    title = "Rol base"
    code = "role_builtin"


class RoleInUseError(AppError):
    status = 409
    title = "Rol en uso"
    code = "role_in_use"


class InvalidPermissionError(AppError):
    status = 422
    title = "Permiso desconocido"
    code = "permission_invalid"


class PermissionEscalationError(AppError):
    """Se intenta dar un permiso (o ser admin de instancia) que quien lo pide no tiene."""

    status = 403
    title = "No puedes dar permisos que no tienes"
    code = "permission_escalation"


class LastTenantManagerError(AppError):
    """El tenant se quedaría sin ningún usuario activo que gestione usuarios."""

    status = 409
    title = "Último gestor de usuarios del tenant"
    code = "last_tenant_manager"
