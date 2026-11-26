"""Administración de usuarios: alta, edición, bloqueo (desactivación), reactivación y borrado (ADR-016).

Desde la Fase 9 cada usuario pertenece a un tenant y tiene un rol de ese tenant (``role_id``); ``is_instance_admin``
da lo que es del servidor. Las consultas reciben el tenant (ADR-013) y las salvaguardas impiden quedarse sin admin de
instancia o sin quien gestione los usuarios de un tenant, y dar permisos que uno no tiene.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

from sqlalchemy import and_, delete, func, not_, or_, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import (
    ACTIVE_RUN_STATUSES,
    DEFAULT_TENANT_ID,
    Project,
    ProjectMember,
    Run,
    TenantRole,
    User,
    UserSession,
    utcnow,
)
from app.db.results import affected_rows
from app.domain.identity import audit
from app.domain.identity.audit import CLI_CONTEXT, AuditAction, RequestContext
from app.domain.identity.errors import (
    LastAdminError,
    SelfModificationError,
    UserDeletionConflictError,
    UsernameTakenError,
    UserNotFoundError,
)
from app.domain.identity.passwords import check_policy, hash_password
from app.domain.identity.sessions import revoke_user_sessions
from app.domain.listing import ListQuery, apply_search, apply_sort
from app.domain.tenancy import roles as tenant_roles
from app.domain.tenancy.errors import LastTenantManagerError, PermissionEscalationError
from app.domain.tenancy.tenants import get_tenant

logger = logging.getLogger(__name__)

USERS_MANAGE = "users.manage"


def normalize_username(username: str) -> str:
    """Los nombres de usuario no distinguen mayúsculas."""
    return username.strip().lower()


@dataclass(frozen=True)
class UserChanges:
    """Cambios de un ``PATCH``; ``None`` significa «sin cambio»."""

    display_name: str | None = None
    role_id: int | None = None
    is_instance_admin: bool | None = None
    tenant_id: int | None = None
    is_active: bool | None = None
    password: str | None = None
    unlock: bool = False
    #: Motivo de desactivar o reactivar (2.7): solo va a la auditoría (``details.reason``).
    reason: str | None = None


def get_user(db: Session, user_id: int, *, tenant_id: int | None) -> User:
    """Usuario por id, del tenant ``tenant_id`` (``None``: de cualquiera, solo para el admin de instancia).

    Raises:
        UserNotFoundError: No existe o es de otro tenant (no se revela cuál).
    """
    user = db.get(User, user_id)
    if user is None or (tenant_id is not None and user.tenant_id != tenant_id):
        raise UserNotFoundError()
    return user


COLOR_SCHEMES: Final = frozenset({"auto", "light", "dark"})


def set_color_scheme(db: Session, user: User, color_scheme: str) -> None:
    """Guarda el tema de la interfaz de ``user`` (``auto``, ``light`` o ``dark``).

    Raises:
        ValueError: si ``color_scheme`` no es uno de :data:`COLOR_SCHEMES`.
    """
    if color_scheme not in COLOR_SCHEMES:
        raise ValueError(f"Tema no válido: {color_scheme!r}")
    if user.color_scheme != color_scheme:
        user.color_scheme = color_scheme
        db.commit()


LANGUAGES: Final = frozenset({"es", "en"})


def set_language(db: Session, user: User, language: str) -> None:
    """Guarda el idioma de la interfaz de ``user`` (``es`` o ``en``).

    Raises:
        ValueError: si ``language`` no es uno de :data:`LANGUAGES`.
    """
    if language not in LANGUAGES:
        raise ValueError(f"Idioma no válido: {language!r}")
    if user.language != language:
        user.language = language
        db.commit()


def get_by_username(db: Session, username: str) -> User | None:
    """Usuario por nombre (normalizado; único en la instancia) o ``None``."""
    return db.scalar(select(User).where(User.username == normalize_username(username)))


#: Estados por los que se filtra la lista de usuarios (2.7), con la regla de la insignia de la interfaz: ``active``
#: (activo y sin bloqueo por intentos vigente), ``inactive`` (desactivado) y ``locked`` (activo y bloqueado por intentos).
USER_STATUSES: Final = ("active", "inactive", "locked")


@dataclass(frozen=True)
class UserFilters:
    """Filtros exactos de la lista de usuarios (2.7), además del texto."""

    role_id: int | None = None
    status: str | None = None
    instance_admin: bool | None = None


def list_users(
    db: Session,
    *,
    tenant_id: int,
    q: str | None,
    limit: int,
    offset: int,
    listing: ListQuery | None = None,
    filters: UserFilters | None = None,
) -> tuple[list[User], int]:
    """Usuarios del tenant (por nombre de usuario si no se pide otro orden), filtrados por texto en usuario, nombre
    visible o rol, y por rol, estado o admin de instancia."""
    listing = listing or ListQuery()
    filters = filters or UserFilters()
    query = select(User).join(TenantRole, TenantRole.id == User.role_id).where(User.tenant_id == tenant_id)
    query = apply_search(query, q or listing.q, [User.username, User.display_name, TenantRole.name])
    if filters.role_id is not None:
        query = query.where(User.role_id == filters.role_id)
    if filters.instance_admin is not None:
        query = query.where(User.is_instance_admin.is_(filters.instance_admin))
    if filters.status is not None:
        now = utcnow()
        locked = and_(User.locked_until.is_not(None), User.locked_until > now)
        if filters.status == "inactive":
            query = query.where(User.is_active.is_(False))
        elif filters.status == "locked":
            query = query.where(User.is_active.is_(True), locked)
        else:
            query = query.where(User.is_active.is_(True), not_(locked))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    columns = {
        "username": User.username,
        "display_name": func.lower(User.display_name),
        "role": func.lower(TenantRole.name),
        "status": User.is_active,
        "created_at": User.created_at,
    }
    query = apply_sort(query, listing, columns, default=[User.username], tiebreak=User.id)
    rows = db.scalars(query.limit(limit).offset(offset)).all()
    return list(rows), total


def lookup_users(db: Session, *, tenant_id: int, q: str, limit: int = 20) -> list[User]:
    """Usuarios **activos** del tenant cuyo usuario o nombre visible empieza por ``q`` (para invitar a un proyecto)."""
    prefix = q.strip().lower()
    if not prefix:
        return []
    query = (
        select(User)
        .where(
            User.tenant_id == tenant_id,
            User.is_active.is_(True),
            or_(
                User.username.startswith(prefix, autoescape=True),
                func.lower(User.display_name).startswith(prefix, autoescape=True),
            ),
        )
        .order_by(User.username)
        .limit(limit)
    )
    return list(db.scalars(query))


def _active_instance_admins(db: Session) -> int:
    return db.scalar(select(func.count()).where(User.is_instance_admin.is_(True), User.is_active.is_(True))) or 0


def active_instance_admins(db: Session) -> int:
    """Administradores de la instancia activos (F0, 2.7: siempre debe haber al menos uno)."""
    return _active_instance_admins(db)


def ensure_instance_admin(db: Session) -> None:
    """Comprueba, **después** de aplicar un cambio (``flush``), que queda algún admin de instancia activo (F0, 2.7).

    Es la segunda barrera tras la comprobación previa. Quien llama no confirma y la petición deshace el cambio.

    Raises:
        LastAdminError: No queda ninguno.
    """
    db.flush()
    if _active_instance_admins(db) == 0:
        raise LastAdminError()


def warn_if_no_instance_admin(db: Session) -> bool:
    """Al arrancar la API o el worker (F0, 2.7): ``logger.critical`` si no hay ningún admin de instancia activo.

    Con la API no se puede llegar a cero; sí restaurando una copia o editando la BD. Devuelve si hay alguno (una BD
    sin migrar no se considera un fallo: lo dirá la migración).
    """
    try:
        count = _active_instance_admins(db)
    except SQLAlchemyError:
        return True
    if count == 0:
        logger.critical(
            "No hay ningún administrador de la instancia activo: recupera uno con «python -m app.cli recover-admin»",
            extra={"event": "no_active_instance_admin"},
        )
    return count > 0


def _lock_user_row(db: Session, user: User) -> None:
    """Escribe en la fila de ``user`` para tomar el bloqueo de escritura de SQLite antes de contar (F0, ADR-016).

    Dos peticiones que quiten a los dos últimos admins (o gestores) se serializan: la segunda espera
    (``busy_timeout``) y cuenta ya con el cambio de la primera, en lugar de un recuento obsoleto.
    """
    db.execute(update(User).where(User.id == user.id).values(updated_at=utcnow()))


def _managers(db: Session, tenant_id: int, *, excluding: int) -> int:
    """Usuarios activos del tenant (sin ``excluding``) con ``users.manage``."""
    rows = db.execute(
        select(TenantRole.permissions)
        .join(User, User.role_id == TenantRole.id)
        .where(User.tenant_id == tenant_id, User.is_active.is_(True), User.id != excluding)
    )
    return sum(1 for (permissions,) in rows if USERS_MANAGE in (permissions or []))


def check_can_manage(actor: User, target: User) -> None:
    """``actor`` tiene todo lo que tiene ``target``: si no, gestionarlo (p. ej. restablecer su contraseña) sería
    quedarse con más permisos de los propios.

    Raises:
        PermissionEscalationError: ``target`` es admin de instancia y ``actor`` no, o el rol de ``target`` tiene algún
            permiso que ``actor`` no tiene.
    """
    if actor.is_instance_admin or actor.id == target.id:
        return
    if target.is_instance_admin:
        raise PermissionEscalationError("Solo un administrador de la instancia gestiona a otro.")
    tenant_roles.check_grant(actor, list(target.role.permissions or []))


def _resolve_role(db: Session, tenant_id: int, role_id: int | None, actor: User | None) -> TenantRole:
    """Rol ``role_id`` del tenant (o «Usuario» si es ``None``) que ``actor`` puede asignar."""
    role = (
        tenant_roles.builtin_role(db, tenant_id, "user")
        if role_id is None
        else tenant_roles.get_role(db, role_id, tenant_id=tenant_id)
    )
    if actor is not None:
        tenant_roles.check_grant(actor, list(role.permissions or []))
    return role


def create_user(
    db: Session,
    *,
    username: str,
    display_name: str,
    password: str,
    settings: Settings,
    ctx: RequestContext,
    actor: User | None,
    tenant_id: int = DEFAULT_TENANT_ID,
    role_id: int | None = None,
    is_instance_admin: bool = False,
) -> User:
    """Crea un usuario activo del tenant y lo audita. ``actor`` es ``None`` en el CLI (primer admin).

    Raises:
        UsernameTakenError: El nombre ya existe (en toda la instancia).
        PasswordPolicyError: La contraseña no cumple la política.
        RoleNotFoundError: El rol no es del tenant.
        PermissionEscalationError: ``actor`` da un rol con permisos que no tiene, o la condición de admin de instancia
            sin serlo.
    """
    if actor is not None and is_instance_admin and not actor.is_instance_admin:
        raise PermissionEscalationError("Solo un administrador de la instancia crea otro.")
    get_tenant(db, tenant_id)
    username = normalize_username(username)
    check_policy(password, username=username, min_length=settings.password_min_length)
    if get_by_username(db, username) is not None:
        raise UsernameTakenError()
    role = _resolve_role(db, tenant_id, role_id, actor)
    user = User(
        tenant_id=tenant_id,
        username=username,
        display_name=display_name.strip() or username,
        password_hash=hash_password(password),
        role_id=role.id,
        is_instance_admin=is_instance_admin,
        is_active=True,
        failed_attempts=0,
    )
    db.add(user)
    db.flush()
    audit.record(
        db,
        action=AuditAction.USER_CREATE,
        ctx=ctx,
        actor_id=actor.id if actor else None,
        target_type="user",
        target_id=user.id,
        details={"username": user.username, "role": role.name, "instance_admin": is_instance_admin},
        tenant_id=tenant_id,
    )
    db.commit()
    return user


def _move(db: Session, user: User, tenant_id: int, role: TenantRole, *, actor: User, ctx: RequestContext) -> None:
    """Pasa ``user`` a otro tenant: pierde sus membresías de proyecto y sus sesiones."""
    old = user.tenant_id
    result = db.execute(delete(ProjectMember).where(ProjectMember.user_id == user.id))
    removed = affected_rows(result)
    user.tenant_id = tenant_id
    user.role_id = role.id
    revoke_user_sessions(db, user.id)
    audit.record(
        db,
        action=AuditAction.USER_MOVE,
        ctx=ctx,
        actor_id=actor.id,
        target_type="user",
        target_id=user.id,
        details={"from_tenant": old, "to_tenant": tenant_id, "memberships_removed": removed},
    )


@dataclass(frozen=True)
class _UpdatePlan:
    """Qué cambia en una edición de usuario, calculado antes de tocar nada."""

    moving: bool
    new_tenant: int
    instance_change: bool
    new_role: TenantRole | None
    loses_instance_admin: bool
    loses_manager: bool


def _plan_update(db: Session, user: User, changes: UserChanges, actor: User) -> _UpdatePlan:
    """Calcula el cambio y comprueba los permisos de ``actor`` y la auto-modificación."""
    check_can_manage(actor, user)
    moving = changes.tenant_id is not None and changes.tenant_id != user.tenant_id
    new_tenant = changes.tenant_id if moving and changes.tenant_id is not None else user.tenant_id
    instance_change = changes.is_instance_admin is not None and changes.is_instance_admin != user.is_instance_admin
    if (moving or instance_change) and not actor.is_instance_admin:
        raise PermissionEscalationError("Solo un administrador de la instancia puede hacerlo.")
    new_role: TenantRole | None = None
    if moving or (changes.role_id is not None and changes.role_id != user.role_id):
        new_role = _resolve_role(db, new_tenant, changes.role_id, actor)
    deactivating = changes.is_active is False and user.is_active
    if user.id == actor.id and (deactivating or new_role is not None or moving or changes.is_instance_admin is False):
        raise SelfModificationError()

    loses_instance_admin = (
        user.is_instance_admin and user.is_active and (deactivating or changes.is_instance_admin is False)
    )
    loses_manager = (
        user.is_active
        and USERS_MANAGE in (user.role.permissions or [])
        and (deactivating or moving or (new_role is not None and USERS_MANAGE not in (new_role.permissions or [])))
    )
    return _UpdatePlan(moving, new_tenant, instance_change, new_role, loses_instance_admin, loses_manager)


def _guard_last_admins(db: Session, user: User, plan: _UpdatePlan, actor: User) -> None:
    """La instancia no se queda sin administradores activos ni el tenant sin quien gestione sus usuarios."""
    if plan.loses_instance_admin or plan.loses_manager:
        _lock_user_row(db, user)  # F0: contar ya con el bloqueo de escritura tomado
    if plan.loses_instance_admin and _active_instance_admins(db) <= 1:
        raise LastAdminError()
    if plan.loses_manager and not actor.is_instance_admin and _managers(db, user.tenant_id, excluding=user.id) == 0:
        raise LastTenantManagerError()


def _apply_profile_and_role(
    db: Session, user: User, changes: UserChanges, plan: _UpdatePlan, *, actor: User, ctx: RequestContext
) -> list[str]:
    """Nombre visible, rol, tenant y admin de instancia; devuelve los campos cambiados que se auditan juntos."""
    changed: list[str] = []
    if changes.display_name is not None and changes.display_name.strip() != user.display_name:
        user.display_name = changes.display_name.strip() or user.username
        changed.append("display_name")
    if plan.moving and plan.new_role is not None:
        _move(db, user, plan.new_tenant, plan.new_role, actor=actor, ctx=ctx)
    elif plan.new_role is not None:
        user.role_id = plan.new_role.id
        revoke_user_sessions(db, user.id)
        changed.append("role")
    if plan.instance_change and changes.is_instance_admin is not None:
        user.is_instance_admin = changes.is_instance_admin
        revoke_user_sessions(db, user.id)
        changed.append("is_instance_admin")
    return changed


def _reset_password(
    db: Session, user: User, password: str, *, actor: User, settings: Settings, ctx: RequestContext
) -> None:
    """Contraseña nueva: quita el bloqueo por intentos y revoca las sesiones."""
    check_policy(password, username=user.username, min_length=settings.password_min_length)
    user.password_hash = hash_password(password)
    user.password_changed_at = utcnow()
    user.failed_attempts = 0
    user.locked_until = None
    revoke_user_sessions(db, user.id)
    audit.record(
        db,
        action=AuditAction.USER_PASSWORD_RESET,
        ctx=ctx,
        actor_id=actor.id,
        target_type="user",
        target_id=user.id,
    )


def _unlock(db: Session, user: User, *, actor: User, ctx: RequestContext) -> None:
    """Quita el bloqueo por intentos, si lo hay."""
    if user.locked_until is not None or user.failed_attempts:
        user.failed_attempts = 0
        user.locked_until = None
        audit.record(
            db, action=AuditAction.USER_UNLOCK, ctx=ctx, actor_id=actor.id, target_type="user", target_id=user.id
        )


def _set_active(db: Session, user: User, active: bool, reason: str | None, *, actor: User, ctx: RequestContext) -> None:
    """Desactivar revoca las sesiones; reactivar quita el bloqueo por intentos."""
    user.is_active = active
    if active:
        user.failed_attempts = 0
        user.locked_until = None
    else:
        revoke_user_sessions(db, user.id)
    reason = (reason or "").strip()
    audit.record(
        db,
        action=AuditAction.USER_REACTIVATE if active else AuditAction.USER_DEACTIVATE,
        ctx=ctx,
        actor_id=actor.id,
        target_type="user",
        target_id=user.id,
        details={"reason": reason} if reason else None,
    )


def _audit_update(
    db: Session, user: User, changed: list[str], plan: _UpdatePlan, *, actor: User, ctx: RequestContext
) -> None:
    """Un único ``user.update`` con los campos de perfil, rol y admin de instancia cambiados."""
    details: dict[str, object] = {"fields": changed}
    if "role" in changed and plan.new_role is not None:
        details["role"] = plan.new_role.name
    if "is_instance_admin" in changed:
        details["instance_admin"] = user.is_instance_admin
    audit.record(
        db,
        action=AuditAction.USER_UPDATE,
        ctx=ctx,
        actor_id=actor.id,
        target_type="user",
        target_id=user.id,
        details=details,
    )


def update_user(
    db: Session, user: User, changes: UserChanges, *, actor: User, settings: Settings, ctx: RequestContext
) -> User:
    """Aplica ``changes`` a ``user``.

    Desactivar, restablecer la contraseña, cambiar de rol o de tenant revoca las sesiones del usuario; reactivar,
    restablecer la contraseña o ``unlock`` quitan el bloqueo por intentos.

    Raises:
        SelfModificationError: Se intenta desactivar, cambiar de rol o de tenant, o quitarse ser admin de instancia a
            sí mismo.
        LastAdminError: Quedaría la instancia sin administradores activos.
        LastTenantManagerError: El tenant se quedaría sin quien gestione sus usuarios.
        PermissionEscalationError: ``user`` tiene permisos que ``actor`` no tiene (o es admin de instancia), se da un
            rol con permisos que ``actor`` no tiene, o algo que solo hace el admin de instancia (marcar admins de
            instancia, mover de tenant).
        PasswordPolicyError: La contraseña nueva no cumple la política.
    """
    plan = _plan_update(db, user, changes, actor)
    _guard_last_admins(db, user, plan, actor)

    changed = _apply_profile_and_role(db, user, changes, plan, actor=actor, ctx=ctx)
    if changes.password is not None:
        _reset_password(db, user, changes.password, actor=actor, settings=settings, ctx=ctx)
    if changes.unlock:
        _unlock(db, user, actor=actor, ctx=ctx)
    if changes.is_active is not None and changes.is_active != user.is_active:
        _set_active(db, user, changes.is_active, changes.reason, actor=actor, ctx=ctx)
    if changed:
        _audit_update(db, user, changed, plan, actor=actor, ctx=ctx)
    if plan.loses_instance_admin:
        ensure_instance_admin(db)
    db.commit()
    db.refresh(user)
    return user


@dataclass(frozen=True)
class ProjectRef:
    """Proyecto citado por la comprobación de borrado: solo id, nombre y rol del usuario."""

    id: int
    name: str
    role: str


@dataclass(frozen=True)
class DeletionCheck:
    """Qué impide borrar a un usuario y qué se borraría con él (ADR-016)."""

    reasons: list[str]
    sole_owner_projects: list[ProjectRef]
    memberships: list[ProjectRef]
    active_runs: int
    sessions: int

    @property
    def can_delete(self) -> bool:
        return not self.reasons

    def as_problem(self) -> dict[str, object]:
        """Extensiones del ``409``: lo mismo que ``GET .../deletion-check``."""
        return {
            "can_delete": self.can_delete,
            "reasons": list(self.reasons),
            "sole_owner_projects": [{"id": p.id, "name": p.name, "role": p.role} for p in self.sole_owner_projects],
            "memberships": [{"id": p.id, "name": p.name, "role": p.role} for p in self.memberships],
            "active_runs": self.active_runs,
            "sessions": self.sessions,
        }


def deletion_check(db: Session, user: User, *, actor: User) -> DeletionCheck:
    """Comprueba si ``user`` se puede borrar sin dejar nada huérfano (ADR-016).

    Bloquean (``reasons``, en este orden): ``self``, ``last_instance_admin`` (último admin de instancia activo),
    ``last_manager`` (último gestor activo del tenant, salvo que actúe un admin de instancia, como al desactivar),
    ``sole_owner`` (único ``owner`` de algún proyecto) y ``active_runs`` (runs suyos en cola o en marcha). Ser miembro,
    también ``owner`` junto a otros, no bloquea: la pertenencia se borra con la cuenta.
    """
    owners = (
        select(ProjectMember.project_id, func.count().label("owners"))
        .where(ProjectMember.role == "owner")
        .group_by(ProjectMember.project_id)
        .subquery()
    )
    rows = db.execute(
        select(Project.id, Project.name, ProjectMember.role, owners.c.owners)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .outerjoin(owners, owners.c.project_id == Project.id)
        .where(ProjectMember.user_id == user.id)
        .order_by(func.lower(Project.name), Project.id)
    ).all()
    memberships = [ProjectRef(id=pid, name=name, role=role) for pid, name, role, _ in rows]
    sole = [
        ProjectRef(id=pid, name=name, role=role) for pid, name, role, count in rows if role == "owner" and count == 1
    ]
    active_runs = (
        db.scalar(select(func.count()).where(Run.created_by == user.id, Run.status.in_(ACTIVE_RUN_STATUSES))) or 0
    )
    sessions = db.scalar(select(func.count()).where(UserSession.user_id == user.id)) or 0
    reasons: list[str] = []
    if user.id == actor.id:
        reasons.append("self")
    if user.is_instance_admin and user.is_active and _active_instance_admins(db) <= 1:
        reasons.append("last_instance_admin")
    if (
        user.is_active
        and USERS_MANAGE in (user.role.permissions or [])
        and not actor.is_instance_admin
        and _managers(db, user.tenant_id, excluding=user.id) == 0
    ):
        reasons.append("last_manager")
    if sole:
        reasons.append("sole_owner")
    if active_runs:
        reasons.append("active_runs")
    return DeletionCheck(
        reasons=reasons, sole_owner_projects=sole, memberships=memberships, active_runs=active_runs, sessions=sessions
    )


def delete_user(db: Session, user: User, *, actor: User, ctx: RequestContext) -> None:
    """Borra ``user`` si no deja nada huérfano (ADR-016) y lo confirma.

    Primero escribe en su fila (bloqueo de escritura de SQLite): nadie puede hacerlo único ``owner`` ni encolarle un run
    entre la comprobación y el ``DELETE``. Se borran en cascada sus sesiones y pertenencias; runs, artefactos,
    plantillas y auditoría quedan sin usuario (``SET NULL``), y la auditoría conserva su nombre (``actor_name``).

    Raises:
        PermissionEscalationError: ``user`` tiene permisos que ``actor`` no tiene (o es admin de instancia).
        UserDeletionConflictError: Algo depende de él (``reasons``).
        LastAdminError: Tras borrar no quedaría ningún admin de instancia activo (segunda barrera de F0).
    """
    check_can_manage(actor, user)
    _lock_user_row(db, user)
    check = deletion_check(db, user, actor=actor)
    if not check.can_delete:
        db.rollback()
        raise UserDeletionConflictError(check.as_problem())
    audit.record(
        db,
        action=AuditAction.USER_DELETE,
        ctx=ctx,
        actor_id=actor.id,
        target_type="user",
        target_id=user.id,
        tenant_id=user.tenant_id,
        details={
            "username": user.username,
            "role": user.role.name,
            "instance_admin": user.is_instance_admin,
            "sessions_closed": check.sessions,
            "memberships_removed": [{"id": p.id, "name": p.name, "role": p.role} for p in check.memberships],
        },
    )
    user_id = user.id
    db.flush()
    db.expunge(user)
    db.execute(delete(User).where(User.id == user_id))
    ensure_instance_admin(db)
    db.commit()


def recover_admin(db: Session, username: str, *, password: str | None, settings: Settings) -> User:
    """Recupera el acceso de administrador desde la CLI (F0, 2.7).

    Reactiva ``username``, quita el bloqueo por intentos, lo marca como admin de instancia y, si se da, cambia su
    contraseña (con la política). Cierra sus sesiones y lo audita como ``user.recover`` (actor: la CLI).

    Raises:
        UserNotFoundError: No existe.
        PasswordPolicyError: La contraseña no cumple la política.
    """
    user = get_by_username(db, username)
    if user is None:
        raise UserNotFoundError()
    if password is not None:
        check_policy(password, username=user.username, min_length=settings.password_min_length)
        user.password_hash = hash_password(password)
        user.password_changed_at = utcnow()
    was = {"active": user.is_active, "instance_admin": user.is_instance_admin}
    user.is_active = True
    user.is_instance_admin = True
    user.failed_attempts = 0
    user.locked_until = None
    closed = revoke_user_sessions(db, user.id)
    audit.record(
        db,
        action=AuditAction.USER_RECOVER,
        ctx=CLI_CONTEXT,
        actor_id=None,
        target_type="user",
        target_id=user.id,
        tenant_id=user.tenant_id,
        details={"was": was, "password_changed": password is not None, "sessions_closed": closed},
    )
    db.commit()
    db.refresh(user)
    return user
