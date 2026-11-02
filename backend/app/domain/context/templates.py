"""Plantillas de taxonomía (WB-7.1): las incluidas en doc_organize (solo lectura) y las personalizadas en la BD.

Una personalizada no puede usar el nombre de una incluida (decisión C2): para cambiar una incluida se duplica con otro
nombre. El Markdown lo valida doc_organize (``parse_taxonomy_template``, L-8c) antes de guardarlo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from functools import cache
from typing import Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import TaxonomyTemplate, User
from app.domain.context.errors import TemplateBuiltinError, TemplateInvalidError, TemplateNotFoundError
from app.domain.identity import audit
from app.domain.identity.audit import AuditAction, RequestContext
from app.domain.runs.operations import MAX_TEMPLATE_BYTES
from app.integrations.doc_organize import context as library

NAME_PATTERN: Final = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


@dataclass(frozen=True)
class TemplateView:
    """Plantilla tal como la ve el cliente; ``markdown`` y el catálogo solo al pedir una."""

    name: str
    title: str | None
    description: str | None
    builtin: bool
    updated_at: datetime | None = None
    markdown: str | None = None
    domains: list[tuple[str, str]] = field(default_factory=list)
    material_types: list[tuple[str, str]] = field(default_factory=list)


@cache
def _builtins() -> dict[str, library.TemplateInfo]:
    """Plantillas incluidas (fijas para una versión de doc_organize: se leen una vez por proceso)."""
    return library.builtin_templates()


def is_builtin(name: str) -> bool:
    return name in _builtins()


def check_name(name: str) -> None:
    """Raises: TemplateInvalidError si ``name`` no es un slug de 1–64 caracteres (minúsculas, dígitos y guiones)."""
    if not NAME_PATTERN.match(name):
        raise TemplateInvalidError("El nombre solo admite minúsculas, dígitos y guiones (hasta 64), p. ej. «sgi-2026».")


def validate_markdown(markdown: str) -> library.TemplateInfo:
    """Valida el Markdown de una plantilla o manifiesto.

    Raises:
        TemplateInvalidError: Demasiado grande o doc_organize lo rechaza (con su mensaje).
    """
    if len(markdown.encode("utf-8")) > MAX_TEMPLATE_BYTES:
        raise TemplateInvalidError(f"La plantilla pasa de {MAX_TEMPLATE_BYTES // 1024} KiB.")
    try:
        return library.parse_template(markdown)
    except library.TemplateInvalidError as exc:
        raise TemplateInvalidError(str(exc)) from None


def _custom(db: Session, tenant_id: int, name: str) -> TaxonomyTemplate | None:
    return db.scalar(
        select(TaxonomyTemplate).where(TaxonomyTemplate.tenant_id == tenant_id, TaxonomyTemplate.name == name)
    )


def list_templates(db: Session, user: User) -> list[TemplateView]:
    """Incluidas y personalizadas del tenant, por nombre."""
    views = [
        TemplateView(name=name, title=info.title, description=info.description, builtin=True)
        for name, info in _builtins().items()
    ]
    rows = db.scalars(select(TaxonomyTemplate).where(TaxonomyTemplate.tenant_id == user.tenant_id))
    views.extend(
        TemplateView(name=r.name, title=r.title, description=r.description, builtin=False, updated_at=r.updated_at)
        for r in rows
    )
    return sorted(views, key=lambda v: v.name)


def get_template(db: Session, user: User, name: str) -> TemplateView:
    """Plantilla ``name`` con su Markdown y su catálogo.

    Raises:
        TemplateNotFoundError: No existe.
    """
    if is_builtin(name):
        info = _builtins()[name]
        markdown = library.builtin_template_markdown(name)
        return TemplateView(
            name=name,
            title=info.title,
            description=info.description,
            builtin=True,
            markdown=markdown,
            domains=info.domains,
            material_types=info.material_types,
        )
    row = _custom(db, user.tenant_id, name)
    if row is None:
        raise TemplateNotFoundError()
    try:
        info = library.parse_template(row.markdown)
    except library.TemplateInvalidError:  # válida al guardarla, pero no para esta versión de doc_organize
        info = library.TemplateInfo(title=row.title, description=row.description, domains=[], material_types=[])
    return TemplateView(
        name=row.name,
        title=row.title,
        description=row.description,
        builtin=False,
        updated_at=row.updated_at,
        markdown=row.markdown,
        domains=info.domains,
        material_types=info.material_types,
    )


def template_markdown(db: Session, user: User, name: str) -> str:
    """Markdown vigente de la plantilla ``name`` (para encolar ``context_build``).

    Raises:
        TemplateNotFoundError: No existe.
    """
    view = get_template(db, user, name)
    if view.markdown is None:  # pragma: no cover - una incluida siempre se renderiza
        raise TemplateNotFoundError()
    return view.markdown


def save_template(
    db: Session, actor: User, name: str, markdown: str, *, ctx: RequestContext
) -> tuple[TemplateView, bool]:
    """Crea o sustituye la plantilla personalizada ``name``; devuelve la vista y si se ha creado.

    Raises:
        TemplateInvalidError: Nombre o Markdown no válidos.
        TemplateBuiltinError: El nombre es de una incluida.
    """
    check_name(name)
    if is_builtin(name):
        raise TemplateBuiltinError("Ese nombre es de una plantilla incluida: duplícala con otro nombre.")
    info = validate_markdown(markdown)
    row = _custom(db, actor.tenant_id, name)
    created = row is None
    if row is None:
        row = TaxonomyTemplate(tenant_id=actor.tenant_id, name=name, created_by=actor.id, markdown=markdown)
        db.add(row)
    row.markdown = markdown
    row.title = info.title[:256] if info.title else None
    row.description = info.description[:1024] if info.description else None
    db.flush()
    audit.record(
        db,
        action=AuditAction.TAXONOMY_TEMPLATE_SAVE,
        ctx=ctx,
        actor_id=actor.id,
        target_type="taxonomy_template",
        target_id=row.id,
        details={"name": name, "created": created},
    )
    db.commit()
    return get_template(db, actor, name), created


def delete_template(db: Session, actor: User, name: str, *, ctx: RequestContext) -> None:
    """Borra la plantilla personalizada ``name`` (los contextos ya construidos con ella no cambian).

    Raises:
        TemplateBuiltinError: Es una incluida.
        TemplateNotFoundError: No existe.
    """
    if is_builtin(name):
        raise TemplateBuiltinError("Las plantillas incluidas no se pueden borrar.")
    row = _custom(db, actor.tenant_id, name)
    if row is None:
        raise TemplateNotFoundError()
    audit.record(
        db,
        action=AuditAction.TAXONOMY_TEMPLATE_DELETE,
        ctx=ctx,
        actor_id=actor.id,
        target_type="taxonomy_template",
        target_id=row.id,
        details={"name": name},
    )
    db.delete(row)
    db.commit()
