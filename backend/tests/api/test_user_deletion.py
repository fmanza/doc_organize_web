"""2.7 (ADR-016): bloquear y borrar usuarios, y siempre un administrador de la instancia activo (F0)."""

from __future__ import annotations

import io
import logging
import threading
import time
import uuid
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.cli import main
from app.core.config import Settings
from app.db.models import AuditEntry, Location, ProjectMember, Run, Tenant, User, UserSession
from app.db.session import get_engine
from app.domain.ai import diagnostics
from app.domain.identity import users
from app.domain.identity.audit import CLI_CONTEXT
from app.domain.identity.errors import LastAdminError
from app.domain.identity.users import UserChanges
from app.integrations.doc_organize.diagnostics import DiagnosticsReport
from tests.conftest import ADMIN_PASSWORD, USER_PASSWORD, login_as, project_payload


@pytest.fixture
def project_id(admin_client: TestClient, project_locations: dict[str, Location]) -> int:
    response = admin_client.post("/api/v1/projects", json=project_payload(project_locations))
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


def _member(db: Session, project_id: int, user: User, role: str) -> None:
    db.add(ProjectMember(project_id=project_id, user_id=user.id, role=role))
    db.commit()


def test_delete_user_cascades_sessions_and_memberships_and_keeps_audit_name(
    admin_client: TestClient, make_user: Callable[..., User], db: Session, project_id: int, admin: User
) -> None:
    bea = make_user("bea")
    _member(db, project_id, bea, "editor")
    bea_client = login_as(admin_client, "bea")
    assert bea_client.get("/api/v1/auth/me").status_code == 200
    run_id = str(uuid.uuid4())
    db.add(Run(id=run_id, project_id=project_id, operation="scan", params={}, status="succeeded", created_by=bea.id))
    db.commit()
    bea_id = bea.id

    check = admin_client.get(f"/api/v1/users/{bea_id}/deletion-check").json()
    assert check["can_delete"] is True
    assert check["reasons"] == []
    assert check["memberships"] == [{"id": project_id, "name": "Proyecto A", "role": "editor"}]
    assert check["sessions"] == 1

    assert admin_client.delete(f"/api/v1/users/{bea_id}").status_code == 204

    db.expire_all()
    assert db.get(User, bea_id) is None
    assert db.scalar(select(UserSession).where(UserSession.user_id == bea_id)) is None
    assert db.scalar(select(ProjectMember).where(ProjectMember.user_id == bea_id)) is None
    assert db.get(Run, run_id).created_by is None  # type: ignore[union-attr]
    assert bea_client.get("/api/v1/auth/me").status_code == 401
    entry = db.scalar(select(AuditEntry).where(AuditEntry.action == "user.delete"))
    assert entry is not None and entry.target_id == str(bea_id) and entry.actor_name == admin.username
    assert entry.details is not None and entry.details["username"] == "bea"
    # Sus eventos conservan el nombre: la auditoría lo enseña aunque el usuario ya no exista.
    logins = admin_client.get("/api/v1/audit", params={"action": "auth.login", "actor": "bea"}).json()
    assert logins["items"] and all(i["actor_username"] == "bea" and i["actor_user_id"] is None for i in logins["items"])
    assert admin_client.get(f"/api/v1/users/{bea_id}").status_code == 404


def test_delete_user_conflicts_list_every_reason(
    admin_client: TestClient, make_user: Callable[..., User], db: Session, project_id: int, admin: User
) -> None:
    bea = make_user("bea")
    _member(db, project_id, bea, "owner")
    db.execute(
        ProjectMember.__table__.update()
        .where(ProjectMember.project_id == project_id, ProjectMember.user_id == admin.id)
        .values(role="editor")
    )
    db.add(Run(id=str(uuid.uuid4()), project_id=project_id, operation="scan", params={}, created_by=bea.id))
    db.commit()

    response = admin_client.delete(f"/api/v1/users/{bea.id}")

    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "user_has_dependencies"
    assert body["reasons"] == ["sole_owner", "active_runs"]
    assert body["sole_owner_projects"] == [{"id": project_id, "name": "Proyecto A", "role": "owner"}]
    assert body["active_runs"] == 1
    db.expire_all()
    assert db.get(User, bea.id) is not None
    # Con otro propietario y sin runs vivos, ya se puede.
    _member(db, project_id, make_user("carla"), "owner")
    db.execute(Run.__table__.update().where(Run.created_by == bea.id).values(status="cancelled"))
    db.commit()
    assert admin_client.get(f"/api/v1/users/{bea.id}/deletion-check").json()["can_delete"] is True


def test_cannot_delete_self_nor_last_instance_admin(admin_client: TestClient, admin: User, db: Session) -> None:
    body = admin_client.delete(f"/api/v1/users/{admin.id}").json()
    assert body["reasons"] == ["self", "last_instance_admin"]
    users_page = admin_client.get("/api/v1/users").json()
    assert users_page["active_instance_admins"] == 1


def test_last_tenant_manager_blocks_a_manager_but_not_an_instance_admin(
    client: TestClient, make_user: Callable[..., User], admin: User
) -> None:
    gestor = make_user("gestor", USER_PASSWORD, "admin", instance_admin=False)
    gestora = make_user("gestora", USER_PASSWORD, "admin", instance_admin=False)
    gestor_client = login_as(client, "gestor")
    # Hay dos gestores (más el admin de instancia, que también gestiona): borrar a uno no deja el tenant sin gestores.
    check = gestor_client.get(f"/api/v1/users/{gestora.id}/deletion-check").json()
    assert "last_manager" not in check["reasons"]
    admin_client = login_as(client, admin.username, ADMIN_PASSWORD)
    assert admin_client.delete(f"/api/v1/users/{gestora.id}").status_code == 204
    # El admin de instancia actúa sin la regla del último gestor (como al desactivar).
    assert "last_manager" not in admin_client.get(f"/api/v1/users/{gestor.id}/deletion-check").json()["reasons"]


def test_manager_cannot_delete_an_instance_admin_and_other_tenant_is_404(
    client: TestClient, make_user: Callable[..., User], make_tenant: Callable[..., Tenant], admin: User
) -> None:
    make_user("gestor", USER_PASSWORD, "admin", instance_admin=False)
    gestor_client = login_as(client, "gestor")
    assert gestor_client.delete(f"/api/v1/users/{admin.id}").status_code == 403
    assert gestor_client.get(f"/api/v1/users/{admin.id}/deletion-check").status_code == 403

    other = make_tenant("otro")
    make_user("ajena", USER_PASSWORD, "admin", tenant_id=other.id)
    ajena_client = login_as(client, "ajena")
    assert ajena_client.delete(f"/api/v1/users/{admin.id}").status_code == 404
    page = ajena_client.get("/api/v1/users").json()
    assert page["active_instance_admins"] is None


def test_block_reason_goes_only_to_the_audit(
    admin_client: TestClient, make_user: Callable[..., User], db: Session
) -> None:
    bea = make_user("bea")
    response = admin_client.patch(f"/api/v1/users/{bea.id}", json={"is_active": False, "reason": "  Baja temporal  "})
    assert response.status_code == 200
    assert "reason" not in response.json()
    entry = db.scalar(select(AuditEntry).where(AuditEntry.action == "user.deactivate"))
    assert entry is not None and entry.details == {"reason": "Baja temporal"}
    assert admin_client.patch(f"/api/v1/users/{bea.id}", json={"reason": "x" * 201}).status_code == 422


def test_last_admin_cannot_be_blocked_nor_lose_the_role(
    admin_client: TestClient, make_user: Callable[..., User], admin: User
) -> None:
    other = make_user("otra", ADMIN_PASSWORD, "admin")
    assert admin_client.patch(f"/api/v1/users/{other.id}", json={"is_active": False}).status_code == 200
    other_client = login_as(admin_client, admin.username, ADMIN_PASSWORD)
    # Ya solo queda «admin»: ni quitarle el rol de admin ni borrarlo (lo impide también «self»).
    response = other_client.patch(f"/api/v1/users/{admin.id}", json={"is_instance_admin": False})
    assert response.status_code == 409


def test_concurrent_blocks_of_the_last_two_admins_leave_one(
    migrated: Settings, make_user: Callable[..., User], db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F0: X bloquea a Y mientras Y bloquea a X. Sin serializar, los dos contarían 2 y quedarían 0 admins."""
    x = make_user("equis", ADMIN_PASSWORD, "admin")
    y = make_user("igriega", ADMIN_PASSWORD, "admin")
    db.commit()
    locked = threading.Event()
    original = users._lock_user_row

    def slow_lock(session: Session, user: User) -> None:
        original(session, user)
        if threading.current_thread().name == "first":
            locked.set()
            time.sleep(0.5)  # la segunda petición llega mientras la primera tiene el bloqueo

    monkeypatch.setattr(users, "_lock_user_row", slow_lock)
    factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    results: dict[str, str] = {}

    def block(actor_id: int, target_id: int) -> None:
        name = threading.current_thread().name
        if name == "second":
            locked.wait(5)
        with factory() as session:
            actor = session.get(User, actor_id)
            target = session.get(User, target_id)
            assert actor is not None and target is not None
            try:
                users.update_user(
                    session, target, UserChanges(is_active=False), actor=actor, settings=migrated, ctx=CLI_CONTEXT
                )
                results[name] = "ok"
            except LastAdminError:
                session.rollback()
                results[name] = "last_admin"

    threads = [
        threading.Thread(target=block, args=(x.id, y.id), name="first"),
        threading.Thread(target=block, args=(y.id, x.id), name="second"),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(15)

    assert results == {"first": "ok", "second": "last_admin"}
    db.expire_all()
    assert users.active_instance_admins(db) == 1


def test_ensure_instance_admin_is_the_second_barrier(db: Session, admin: User) -> None:
    admin.is_active = False
    with pytest.raises(LastAdminError):
        users.ensure_instance_admin(db)
    db.rollback()
    assert users.active_instance_admins(db) == 1


def test_recover_admin_reactivates_unlocks_and_sets_password(
    migrated: Settings,
    make_user: Callable[..., User],
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    client: TestClient,
) -> None:
    bea = make_user("bea")
    bea.is_active = False
    bea.failed_attempts = 3
    db.commit()
    monkeypatch.setattr("sys.stdin", io.StringIO("frase-de-paso-nueva\n"))

    assert main(["recover-admin", "--username", "Bea", "--password-stdin"]) == 0

    out = capsys.readouterr()
    assert "frase-de-paso-nueva" not in out.out + out.err
    db.expire_all()
    recovered = db.get(User, bea.id)
    assert recovered is not None and recovered.is_active and recovered.is_instance_admin
    assert recovered.failed_attempts == 0 and recovered.locked_until is None
    entry = db.scalar(select(AuditEntry).where(AuditEntry.action == "user.recover"))
    assert entry is not None and entry.actor_user_id is None and entry.details is not None
    assert entry.details["was"] == {"active": False, "instance_admin": False}
    login_as(client, "bea", "frase-de-paso-nueva")
    assert main(["recover-admin", "--username", "nadie"]) == 1


def test_diagnostics_and_startup_warn_without_active_admins(
    db: Session, admin: User, caplog: pytest.LogCaptureFixture
) -> None:
    empty = DiagnosticsReport(checks=[], checked_at="2026-11-25T00:00:00Z")
    ok = diagnostics.with_instance_admins(empty, db)
    assert [(c.name, c.status) for c in ok.checks] == [("instance_admins", "ok")]

    admin.is_active = False
    db.flush()
    report = diagnostics.with_instance_admins(empty, db)
    assert [(c.name, c.status) for c in report.checks] == [("instance_admins", "error")]
    assert not report.ok
    with caplog.at_level(logging.CRITICAL):
        assert users.warn_if_no_instance_admin(db) is False
    assert any(getattr(r, "event", None) == "no_active_instance_admin" for r in caplog.records)
    db.rollback()


def test_role_update_cannot_leave_the_tenant_without_managers(
    client: TestClient, make_user: Callable[..., User], make_tenant: Callable[..., Tenant], db: Session
) -> None:
    other = make_tenant("otro")
    jefa = make_user("jefa", USER_PASSWORD, "admin", tenant_id=other.id)
    jefa_client = login_as(client, "jefa")
    permissions = ["users.manage", "roles.manage"]
    created = jefa_client.post("/api/v1/roles", json={"name": "Gestión", "permissions": permissions})
    assert created.status_code == 201, created.text
    role_id = created.json()["id"]
    gestor = make_user("gestor-otro", tenant_id=other.id)
    gestor.role_id = role_id
    db.commit()
    # «jefa» gestiona usuarios por su rol base: quitar el permiso al rol personalizado no deja el tenant sin gestores.
    without: dict[str, Any] = {"permissions": ["roles.manage"]}
    assert jefa_client.patch(f"/api/v1/roles/{role_id}", json=without).status_code == 200
    assert jefa_client.patch(f"/api/v1/roles/{role_id}", json={"permissions": permissions}).status_code == 200
    db.refresh(jefa)
    jefa.is_active = False
    db.commit()

    gestor_client = login_as(client, "gestor-otro")
    response = gestor_client.patch(f"/api/v1/roles/{role_id}", json=without)

    assert response.status_code == 409
    assert response.json()["code"] == "last_tenant_manager"
