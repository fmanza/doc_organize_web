"""Tenants (WB-9.1, ADR-013): alta, renombrado y borrado (solo vacíos, decisión E3). Solo el admin de instancia."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Final

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.db.models import (
    DEFAULT_TENANT_ID,
    AuditEntry,
    Location,
    Project,
    TaxonomyTemplate,
    Tenant,
    TenantRole,
    User,
)
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction, RequestContext
from app.domain.listing import ListQuery, apply_search, apply_sort
from app.domain.tenancy.errors import (
    TenantNotEmptyError,
    TenantNotFoundError,
    TenantProtectedError,
    TenantSlugTakenError,
)
from app.domain.tenancy.roles import create_builtin_roles

SLUG: Final = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")


@dataclass(frozen=True)
class TenantView:
    tenant: Tenant
    users: int
    projects: int
    locations: int

    @property
    def empty(self) -> bool:
        return not (self.users or self.projects or self.locations)


def get_tenant(db: Session, tenant_id: int) -> Tenant:
    """Tenant por id.

    Raises:
        TenantNotFoundError: No existe.
    """
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise TenantNotFoundError()
    return tenant


def _count(db: Session, model: type[User] | type[Project] | type[Location] | type[TaxonomyTemplate]) -> dict[int, int]:
    rows = db.execute(select(model.tenant_id, func.count()).group_by(model.tenant_id))
    return {int(tenant_id): int(count) for tenant_id, count in rows}


def _count_column(model: type[User] | type[Project] | type[Location]) -> Any:
    return select(func.count()).where(model.tenant_id == Tenant.id).correlate(Tenant).scalar_subquery()


def list_tenants(
    db: Session, *, limit: int, offset: int, listing: ListQuery | None = None
) -> tuple[list[TenantView], int]:
    """Tenants (por nombre si no se pide otro orden) con sus recuentos (los proyectos incluyen los borrados: siguen en
    el historial), filtrados por texto en el nombre o el identificador."""
    listing = listing or ListQuery()
    query = apply_search(select(Tenant), listing.q, [Tenant.name, Tenant.slug])
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    columns = {
        "name": func.lower(Tenant.name),
        "slug": Tenant.slug,
        "users": _count_column(User),
        "projects": _count_column(Project),
        "locations": _count_column(Location),
    }
    query = apply_sort(query, listing, columns, default=[func.lower(Tenant.name)], tiebreak=Tenant.id)
    rows = db.scalars(query.limit(limit).offset(offset)).all()
    users, projects, locations = _count(db, User), _count(db, Project), _count(db, Location)
    return [TenantView(t, users.get(t.id, 0), projects.get(t.id, 0), locations.get(t.id, 0)) for t in rows], total


def view(db: Session, tenant: Tenant) -> TenantView:
    def count(model: type[User] | type[Project] | type[Location]) -> int:
        return db.scalar(select(func.count()).where(model.tenant_id == tenant.id)) or 0

    return TenantView(tenant, count(User), count(Project), count(Location))


def create_tenant(db: Session, *, slug: str, name: str, actor: User, ctx: RequestContext) -> Tenant:
    """Crea un tenant con sus roles base y lo audita.

    Raises:
        TenantSlugTakenError: El identificador ya existe.
    """
    slug = slug.strip().lower()
    if db.scalar(select(Tenant.id).where(Tenant.slug == slug)) is not None:
        raise TenantSlugTakenError()
    tenant = Tenant(slug=slug, name=name.strip())
    db.add(tenant)
    db.flush()
    create_builtin_roles(db, tenant.id)
    audit.record(
        db,
        action=AuditAction.TENANT_CREATE,
        ctx=ctx,
        actor_id=actor.id,
        target_type="tenant",
        target_id=tenant.id,
        details={"slug": slug, "name": tenant.name},
    )
    db.commit()
    return tenant


def rename_tenant(db: Session, tenant: Tenant, *, name: str, actor: User, ctx: RequestContext) -> Tenant:
    """Cambia el nombre visible (el ``slug`` no cambia)."""
    if name.strip() != tenant.name:
        audit.record(
            db,
            action=AuditAction.TENANT_UPDATE,
            ctx=ctx,
            actor_id=actor.id,
            target_type="tenant",
            target_id=tenant.id,
            details={"name": [tenant.name, name.strip()]},
        )
        tenant.name = name.strip()
        db.commit()
    return tenant


def delete_tenant(db: Session, tenant: Tenant, *, actor: User, ctx: RequestContext) -> None:
    """Borra un tenant **vacío**: sin usuarios (tampoco desactivados), proyectos (tampoco borrados), ubicaciones ni
    plantillas. Se llevan con él sus roles. Su auditoría pasa al tenant ``default`` para no perder el historial.

    Raises:
        TenantProtectedError: Es ``default``.
        TenantNotEmptyError: Tiene algo de lo anterior.
    """
    if tenant.id == DEFAULT_TENANT_ID:
        raise TenantProtectedError()
    current = view(db, tenant)
    templates = db.scalar(select(func.count()).where(TaxonomyTemplate.tenant_id == tenant.id)) or 0
    if not current.empty or templates:
        raise TenantNotEmptyError(
            f"Tiene {current.users} usuarios, {current.projects} proyectos, {current.locations} ubicaciones y "
            f"{templates} plantillas."
        )
    result = db.execute(update(AuditEntry).where(AuditEntry.tenant_id == tenant.id).values(tenant_id=DEFAULT_TENANT_ID))
    moved = int(getattr(result, "rowcount", 0) or 0)
    for role in db.scalars(select(TenantRole).where(TenantRole.tenant_id == tenant.id)):
        db.delete(role)
    audit.record(
        db,
        action=AuditAction.TENANT_DELETE,
        ctx=ctx,
        actor_id=actor.id,
        target_type="tenant",
        target_id=tenant.id,
        details={"slug": tenant.slug, "audit_entries_moved": moved},
        tenant_id=DEFAULT_TENANT_ID,
    )
    db.flush()
    db.delete(tenant)
    db.commit()
