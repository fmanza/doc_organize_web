"""Fase 9: tenants, roles con permisos, selector de tenant y aislamiento entre tenants (IDOR: 404, nunca datos ajenos)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEntry, Location, ProjectMember, Tenant, TenantRole, User
from tests.api.test_context import TEMPLATE
from tests.conftest import ADMIN_PASSWORD, USER_PASSWORD, login_as, project_payload


@pytest.fixture
def admin_api(user_client: TestClient, admin: User) -> TestClient:
    """Admin de instancia en otro cliente (``user_client`` sigue siendo ana, de ``default``)."""
    return login_as(user_client, admin.username, ADMIN_PASSWORD)


@pytest.fixture
def other(make_tenant: Callable[..., Tenant]) -> Tenant:
    return make_tenant("obras", "Obras")


@pytest.fixture
def bea(user_client: TestClient, other: Tenant, make_user: Callable[..., User]) -> TestClient:
    """Administradora (rol base) del tenant ``obras``, sin ser admin de instancia."""
    make_user("bea", USER_PASSWORD, "admin", tenant_id=other.id)
    return login_as(user_client, "bea")


# --- tenants -----------------------------------------------------------------------------------------------------------


def test_tenants_are_for_instance_admins(client: TestClient, user_client: TestClient, bea: TestClient) -> None:
    for caller in (user_client, bea):
        assert caller.get("/api/v1/tenants").status_code == 403
        assert caller.post("/api/v1/tenants", json={"slug": "x-y", "name": "X"}).status_code == 403
    anonymous = TestClient(client.app, base_url="https://testserver")
    assert anonymous.get("/api/v1/tenants").status_code == 401


def test_create_rename_and_delete_an_empty_tenant(admin_api: TestClient, db: Session) -> None:
    created = admin_api.post("/api/v1/tenants", json={"slug": "calidad", "name": "Calidad"})
    assert created.status_code == 201, created.text
    tenant_id = created.json()["id"]
    assert created.json()["empty"] is True
    roles = db.scalars(select(TenantRole.builtin).where(TenantRole.tenant_id == tenant_id)).all()
    assert sorted(r or "" for r in roles) == ["admin", "user"]
    assert admin_api.post("/api/v1/tenants", json={"slug": "calidad", "name": "Otra"}).json()["code"] == (
        "tenant_slug_taken"
    )
    assert admin_api.patch(f"/api/v1/tenants/{tenant_id}", json={"name": "Calidad ISO"}).json()["name"] == "Calidad ISO"

    assert admin_api.delete(f"/api/v1/tenants/{tenant_id}").status_code == 204

    assert db.get(Tenant, tenant_id) is None
    actions = set(db.scalars(select(AuditEntry.action).where(AuditEntry.action.startswith("tenant."))))
    assert actions == {"tenant.create", "tenant.update", "tenant.delete"}


def test_only_empty_tenants_are_deleted(admin_api: TestClient, other: Tenant, bea: TestClient) -> None:
    response = admin_api.delete(f"/api/v1/tenants/{other.id}")
    assert response.status_code == 409 and response.json()["code"] == "tenant_not_empty"
    assert admin_api.delete("/api/v1/tenants/1").json()["code"] == "tenant_protected"
    assert admin_api.delete("/api/v1/tenants/9999").status_code == 404
    page = admin_api.get("/api/v1/tenants").json()
    obras = next(t for t in page["items"] if t["slug"] == "obras")
    assert obras["users"] == 1 and obras["empty"] is False
    users = admin_api.get(f"/api/v1/tenants/{other.id}/users").json()
    assert [u["username"] for u in users["items"]] == ["bea"]


# --- selector de tenant -----------------------------------------------------------------------------------------------


def test_instance_admin_switches_tenant(
    admin_api: TestClient, user_client: TestClient, other: Tenant, db: Session
) -> None:
    assert user_client.put("/api/v1/auth/tenant", json={"tenant_id": other.id}).status_code == 403

    switched = admin_api.put("/api/v1/auth/tenant", json={"tenant_id": other.id})

    assert switched.status_code == 200
    me = admin_api.get("/api/v1/auth/me").json()
    assert me["tenant"]["slug"] == "default" and me["acting_tenant"]["slug"] == "obras"
    assert me["is_instance_admin"] is True and "projects.all" in me["permissions"]
    created = admin_api.post("/api/v1/users", json={"username": "carla", "display_name": "Carla", "password": "x" * 14})
    assert created.status_code == 201 and created.json()["tenant_id"] == other.id
    entry = db.scalars(select(AuditEntry).where(AuditEntry.action == "session.tenant_switch")).one()
    assert entry.tenant_id == other.id
    assert admin_api.put("/api/v1/auth/tenant", json={"tenant_id": None}).json()["acting_tenant"]["slug"] == "default"
    assert admin_api.put("/api/v1/auth/tenant", json={"tenant_id": 9999}).status_code == 404


# --- roles -------------------------------------------------------------------------------------------------------------


def test_roles_crud_with_builtin_and_in_use_rules(bea: TestClient, other: Tenant, db: Session) -> None:
    listed = bea.get("/api/v1/roles").json()["items"]
    assert [r["builtin"] for r in listed] == ["admin", "user"]
    builtin = listed[0]["id"]
    assert bea.patch(f"/api/v1/roles/{builtin}", json={"permissions": []}).json()["code"] == "role_builtin"
    assert bea.delete(f"/api/v1/roles/{builtin}").json()["code"] == "role_builtin"
    assert bea.post("/api/v1/roles", json={"name": "X", "permissions": ["root"]}).json()["code"] == "permission_invalid"

    created = bea.post("/api/v1/roles", json={"name": "Auditoría", "permissions": ["audit.read"]})
    assert created.status_code == 201, created.text
    role_id = created.json()["id"]
    assert bea.post("/api/v1/roles", json={"name": "auditoría", "permissions": []}).json()["code"] == "role_name_taken"
    assert bea.get("/api/v1/permissions").json()["items"][0] == "users.manage"
    user = bea.post(
        "/api/v1/users", json={"username": "dani", "display_name": "Dani", "password": "x" * 14, "role_id": role_id}
    )
    assert user.status_code == 201 and user.json()["role"]["name"] == "Auditoría"
    assert bea.delete(f"/api/v1/roles/{role_id}").json()["code"] == "role_in_use"
    renamed = bea.patch(f"/api/v1/roles/{role_id}", json={"name": "Auditores", "permissions": ["audit.read"]})
    assert renamed.json()["name"] == "Auditores" and renamed.json()["users"] == 1


def test_custom_role_grants_only_its_permissions(bea: TestClient, other: Tenant, user_client: TestClient) -> None:
    role_id = bea.post("/api/v1/roles", json={"name": "Auditoría", "permissions": ["audit.read"]}).json()["id"]
    bea.post(
        "/api/v1/users", json={"username": "dani", "display_name": "Dani", "password": "x" * 14, "role_id": role_id}
    )
    dani = login_as(user_client, "dani", "x" * 14)

    assert dani.get("/api/v1/audit").status_code == 200
    assert dani.get("/api/v1/users").status_code == 403
    assert dani.get("/api/v1/roles").status_code == 403  # ni roles.manage ni users.manage
    assert dani.get("/api/v1/auth/me").json()["permissions"] == ["audit.read"]


def test_nobody_grants_what_they_lack(bea: TestClient, other: Tenant, user_client: TestClient) -> None:
    role_id = bea.post("/api/v1/roles", json={"name": "Roles", "permissions": ["roles.manage", "users.manage"]}).json()[
        "id"
    ]
    bea.post("/api/v1/users", json={"username": "eva", "display_name": "Eva", "password": "x" * 14, "role_id": role_id})
    eva = login_as(user_client, "eva", "x" * 14)

    escalate = eva.post("/api/v1/roles", json={"name": "Todo", "permissions": ["projects.all"]})
    assert escalate.status_code == 403 and escalate.json()["code"] == "permission_escalation"
    admin_role = next(r["id"] for r in eva.get("/api/v1/roles").json()["items"] if r["builtin"] == "admin")
    to_admin = eva.post(
        "/api/v1/users", json={"username": "fer", "display_name": "Fer", "password": "x" * 14, "role_id": admin_role}
    )
    assert to_admin.status_code == 403
    instance = eva.post(
        "/api/v1/users",
        json={"username": "gus", "display_name": "Gus", "password": "x" * 14, "is_instance_admin": True},
    )
    assert instance.status_code == 403


def test_last_tenant_manager_is_kept(bea: TestClient, other: Tenant, db: Session) -> None:
    me = bea.get("/api/v1/auth/me").json()
    user_role = next(r["id"] for r in bea.get("/api/v1/roles").json()["items"] if r["builtin"] == "user")
    # A sí misma no puede cambiarse el rol; otro gestor sin más gestores tampoco la deja sin ninguno.
    assert bea.patch(f"/api/v1/users/{me['id']}", json={"role_id": user_role}).status_code == 409


# --- aislamiento (IDOR) -----------------------------------------------------------------------------------------------


@pytest.fixture
def default_world(
    user_client: TestClient, admin_api: TestClient, project_locations: dict[str, Location]
) -> dict[str, Any]:
    """Recursos de ``default``: un proyecto de ana con un run, una plantilla personalizada y la auditoría."""
    project = user_client.post("/api/v1/projects", json=project_payload(project_locations)).json()
    run = user_client.post(f"/api/v1/projects/{project['id']}/runs", json={"operation": "noop", "steps": 1}).json()
    assert admin_api.put("/api/v1/taxonomy-templates/obras-propia", json={"markdown": TEMPLATE}).status_code in (
        200,
        201,
    )
    return {"project": project, "run": run, "locations": project_locations}


def test_another_tenant_sees_nothing_of_default(
    bea: TestClient, default_world: dict[str, Any], user: User, admin: User, db: Session
) -> None:
    project_id = default_world["project"]["id"]
    run_id = default_world["run"]["id"]
    source = default_world["locations"]["source"].id
    base = f"/api/v1/projects/{project_id}"

    for path in (
        base,
        f"{base}/members",
        f"{base}/documents",
        f"{base}/context",
        f"{base}/scanned-folders",
        f"/api/v1/runs/{run_id}",
        f"/api/v1/runs/{run_id}/events",
        f"/api/v1/locations/{source}",
        f"/api/v1/fs/browse?location_id={source}",
        f"/api/v1/users/{user.id}",
        "/api/v1/taxonomy-templates/obras-propia",
    ):
        assert bea.get(path).status_code == 404, path
    assert bea.post(f"/api/v1/runs/{run_id}/cancel").status_code == 404
    assert bea.post(f"{base}/runs", json={"operation": "noop"}).status_code == 404
    assert bea.patch(f"/api/v1/users/{user.id}", json={"is_active": False}).status_code == 404

    assert bea.get("/api/v1/projects").json()["total"] == 0
    assert bea.get("/api/v1/runs").json()["total"] == 0
    assert bea.get("/api/v1/locations").json()["total"] == 0
    assert [u["username"] for u in bea.get("/api/v1/users").json()["items"]] == ["bea"]
    assert bea.get("/api/v1/users/lookup", params={"q": "an"}).json()["items"] == []
    assert {s["username"] for s in bea.get("/api/v1/sessions").json()["items"]} == {"bea"}
    assert all(e["actor_username"] in (None, "bea") for e in bea.get("/api/v1/audit").json()["items"])
    names = {t["name"] for t in bea.get("/api/v1/taxonomy-templates").json()["items"]}
    assert "obras-propia" not in names
    other_roles = {r.id for r in db.scalars(select(TenantRole).where(TenantRole.tenant_id == 1))}
    assert all(bea.get(f"/api/v1/roles/{role_id}").status_code == 404 for role_id in other_roles)


def test_projects_only_use_their_tenant(
    bea: TestClient, default_world: dict[str, Any], user_client: TestClient, other: Tenant, db: Session
) -> None:
    # Con las ubicaciones de default, un proyecto de obras no existe: 404 de la ubicación.
    response = bea.post("/api/v1/projects", json=project_payload(default_world["locations"], name="Robado"))
    assert response.status_code == 404
    bea_id = db.scalar(select(User.id).where(User.username == "bea"))
    added = user_client.post(
        f"/api/v1/projects/{default_world['project']['id']}/members", json={"user_id": bea_id, "role": "viewer"}
    )
    assert added.status_code in (404, 422), added.text


def test_moving_a_user_drops_memberships_and_sessions(
    admin_api: TestClient,
    default_world: dict[str, Any],
    user: User,
    other: Tenant,
    user_client: TestClient,
    db: Session,
) -> None:
    assert db.scalar(select(ProjectMember).where(ProjectMember.user_id == user.id)) is not None

    moved = admin_api.patch(f"/api/v1/users/{user.id}", json={"tenant_id": other.id})

    assert moved.status_code == 200 and moved.json()["tenant_id"] == other.id
    assert moved.json()["role"]["builtin"] == "user"
    assert user_client.get("/api/v1/auth/me").status_code == 401
    db.expire_all()
    assert db.scalar(select(ProjectMember).where(ProjectMember.user_id == user.id)) is None
    assert (
        db.scalars(select(AuditEntry).where(AuditEntry.action == "user.move")).one().details["memberships_removed"] == 1
    )  # type: ignore[index]


def test_a_used_location_does_not_change_tenant(
    admin_api: TestClient, default_world: dict[str, Any], other: Tenant
) -> None:
    source = default_world["locations"]["source"].id
    response = admin_api.patch(f"/api/v1/locations/{source}", json={"tenant_id": other.id})
    assert response.status_code == 409


def test_a_tenant_admin_cannot_take_over_a_stronger_account(
    user_client: TestClient, admin: User, make_user: Callable[..., User], db: Session
) -> None:
    """Restablecer la contraseña de quien tiene más permisos sería quedarse con ellos (AUDIT_CODE, Fase 9)."""
    make_user("tere", USER_PASSWORD, "admin", instance_admin=False)  # «Administrador» de default, sin ser de instancia
    tere = login_as(user_client, "tere")
    admin_session = login_as(user_client, admin.username, ADMIN_PASSWORD)

    takeover = tere.patch(f"/api/v1/users/{admin.id}", json={"password": "nueva-frase-de-paso-1"})
    assert takeover.status_code == 403 and takeover.json()["code"] == "permission_escalation"
    assert tere.patch(f"/api/v1/users/{admin.id}", json={"is_active": False}).status_code == 403
    sessions = tere.get("/api/v1/sessions", params={"user_id": admin.id}).json()["items"]
    assert sessions and tere.delete(f"/api/v1/sessions/{sessions[0]['id']}").status_code == 403
    assert admin_session.get("/api/v1/auth/me").status_code == 200

    role_id = tere.post("/api/v1/roles", json={"name": "Todo", "permissions": ["projects.all", "audit.read"]}).json()[
        "id"
    ]
    make_user("ugo")
    ugo_id = db.scalar(select(User.id).where(User.username == "ugo"))
    tere.patch(f"/api/v1/users/{ugo_id}", json={"role_id": role_id})
    limited = tere.post("/api/v1/roles", json={"name": "Usuarios", "permissions": ["users.manage"]}).json()["id"]
    make_user("vera")
    vera_id = db.scalar(select(User.id).where(User.username == "vera"))
    tere.patch(f"/api/v1/users/{vera_id}", json={"role_id": limited})
    vera = login_as(user_client, "vera")
    weaker = vera.patch(f"/api/v1/users/{ugo_id}", json={"password": "nueva-frase-de-paso-2"})
    assert weaker.status_code == 403  # ugo tiene projects.all y audit.read, que vera no tiene
