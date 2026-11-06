"""web 1.2.0: búsqueda y orden en todos los listados paginados, y purga de la auditoría por fechas."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, get_args

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1 import listing
from app.db.models import AuditEntry, Location, Run, ScanError, Tenant, User
from tests.api.test_context import _seed_context
from tests.conftest import login_as, project_payload


@pytest.fixture
def project_id(admin_client: TestClient, project_locations: dict[str, Location]) -> int:
    response = admin_client.post("/api/v1/projects", json=project_payload(project_locations))
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


@pytest.fixture
def scan_run(db: Session, project_id: int, admin: User) -> str:
    """Un escaneo terminado con tres errores (ruta, mensaje y reintentos distintos)."""
    run_id = str(uuid.uuid4())
    db.add(
        Run(
            id=run_id,
            project_id=project_id,
            operation="scan",
            params={},
            status="succeeded",
            created_by=admin.id,
            started_at=datetime.now(UTC) - timedelta(minutes=5),
            finished_at=datetime.now(UTC),
        )
    )
    db.flush()
    db.add_all(
        [
            ScanError(run_id=run_id, project_id=project_id, path="2024/b.pdf", message="Zeta roto", retry_count=1),
            ScanError(run_id=run_id, project_id=project_id, path="2024/a.pdf", message="Alfa roto", retry_count=3),
            ScanError(run_id=run_id, project_id=project_id, path="2024/100%_c.pdf", message="Beta", retry_count=2),
        ]
    )
    db.commit()
    return run_id


def _endpoints(project_id: int, run_id: str) -> list[tuple[str, Any]]:
    return [
        ("/api/v1/users", listing.UserSort),
        ("/api/v1/tenants", listing.TenantSort),
        ("/api/v1/tenants/1/users", listing.UserSort),
        ("/api/v1/locations", listing.LocationSort),
        ("/api/v1/projects", listing.ProjectSort),
        ("/api/v1/runs", listing.RunSort),
        ("/api/v1/sessions", listing.SessionSort),
        ("/api/v1/audit", listing.AuditSort),
        (f"/api/v1/runs/{run_id}/scan-errors", listing.ScanErrorSort),
        (f"/api/v1/projects/{project_id}/scan-errors", listing.ScanErrorSort),
        (f"/api/v1/runs/{run_id}/duplicate-groups", listing.GroupSort),
        (f"/api/v1/projects/{project_id}/context/documents", listing.ContextDocumentSort),
    ]


def test_every_sort_key_and_search_work_on_every_list(
    admin_client: TestClient, db: Session, project_id: int, scan_run: str
) -> None:
    """Cada clave del ``Literal`` tiene su columna en el servicio (un desajuste sería un 500)."""
    _seed_context(db, project_id)
    for path, sort in _endpoints(project_id, scan_run):
        for key in get_args(sort):
            for order in ("asc", "desc"):
                response = admin_client.get(path, params={"sort": key, "order": order, "q": "a", "limit": 25})
                assert response.status_code == 200, (path, key, order, response.text)


def test_unknown_sort_or_order_is_rejected(admin_client: TestClient) -> None:
    assert admin_client.get("/api/v1/users", params={"sort": "password_hash"}).status_code == 422
    assert admin_client.get("/api/v1/users", params={"sort": "username", "order": "sideways"}).status_code == 422
    assert admin_client.get("/api/v1/locations", params={"q": "x" * 101}).status_code == 422


def test_scan_errors_sort_and_search(admin_client: TestClient, scan_run: str) -> None:
    path = f"/api/v1/runs/{scan_run}/scan-errors"

    by_retries = admin_client.get(path, params={"sort": "retry_count", "order": "desc"}).json()
    by_message = admin_client.get(path, params={"sort": "message"}).json()
    search = admin_client.get(path, params={"q": "ROTO"}).json()
    literal = admin_client.get(path, params={"q": "100%_"}).json()  # los comodines se buscan como texto

    assert [i["retry_count"] for i in by_retries["items"]] == [3, 2, 1]
    assert [i["message"] for i in by_message["items"]] == ["Alfa roto", "Beta", "Zeta roto"]
    assert search["total"] == 2
    assert [i["path"] for i in literal["items"]] == ["2024/100%_c.pdf"]


def test_users_sort_by_name_and_search_by_role(
    admin_client: TestClient, make_user: Callable[..., User], admin: User, db: Session
) -> None:
    for username, display_name in (("zoe", "Ana"), ("bruno", "Zacarías")):
        make_user(username).display_name = display_name
    db.commit()

    by_name = admin_client.get("/api/v1/users", params={"sort": "display_name"}).json()
    newest = admin_client.get("/api/v1/users", params={"sort": "created_at", "order": "desc"}).json()
    by_role = admin_client.get("/api/v1/users", params={"q": "administra"}).json()

    names = [i["display_name"] for i in by_name["items"]]
    assert names.index("Ana") < names.index("Zacarías")
    assert newest["items"][0]["username"] == "bruno"
    assert [i["username"] for i in by_role["items"]] == [admin.username]


def test_context_documents_sort_by_title(admin_client: TestClient, db: Session, project_id: int) -> None:
    _seed_context(db, project_id)
    base = f"/api/v1/projects/{project_id}/context/documents"

    body = admin_client.get(base, params={"domain": "facturas", "sort": "title"}).json()
    search = admin_client.get(base, params={"domain": "facturas", "q": "enero"}).json()

    assert [i["title"] for i in body["items"]] == ["Factura enero", "Factura febrero"]
    assert search["total"] == 1


# --- purga de la auditoría -------------------------------------------------------------------------------------------


def _entries(db: Session, admin: User, *days_ago: int) -> None:
    now = datetime.now(UTC)
    db.add_all(
        AuditEntry(tenant_id=admin.tenant_id, ts=now - timedelta(days=d), action="test.old", actor_user_id=admin.id)
        for d in days_ago
    )
    db.commit()


def _range(days_from: int, days_to: int) -> dict[str, str]:
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return {
        "since": (today - timedelta(days=days_from)).isoformat(),
        "until": (today - timedelta(days=days_to)).isoformat(),
    }


def test_purge_previews_then_deletes_and_is_audited(admin_client: TestClient, db: Session, admin: User) -> None:
    _entries(db, admin, 40, 35, 31, 10)
    window = _range(45, 30)

    preview = admin_client.post("/api/v1/audit/purge", json={**window, "dry_run": True})
    assert preview.status_code == 200 and preview.json() == {"matched": 3, "deleted": 0}

    stale = admin_client.post("/api/v1/audit/purge", json={**window, "dry_run": False, "confirm_count": 2})
    assert stale.status_code == 409 and stale.json()["code"] == "purge_changed"

    done = admin_client.post("/api/v1/audit/purge", json={**window, "dry_run": False, "confirm_count": 3})
    assert done.json() == {"matched": 3, "deleted": 3}

    db.expire_all()
    left = db.scalars(select(AuditEntry.action).where(AuditEntry.action.in_(["test.old", "audit.purge"]))).all()
    assert sorted(left) == ["audit.purge", "test.old"]  # el de hace 10 días y el registro de la purga
    purge = db.scalars(select(AuditEntry).where(AuditEntry.action == "audit.purge")).one()
    assert purge.details is not None and purge.details["deleted"] == 3


def test_purge_never_touches_today_or_an_empty_range(admin_client: TestClient) -> None:
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = {"since": (today - timedelta(days=3)).isoformat(), "until": (today + timedelta(days=1)).isoformat()}
    backwards = _range(1, 5)
    naive = {"since": "2026-01-01T00:00:00", "until": "2026-02-01T00:00:00"}

    for body, status in ((tomorrow, 422), (backwards, 422), (naive, 422)):
        response = admin_client.post("/api/v1/audit/purge", json={**body, "dry_run": True})
        assert response.status_code == status, body
    assert admin_client.post("/api/v1/audit/purge", json={**tomorrow}).json()["code"] == "purge_range"


def test_only_the_instance_admin_purges(
    user_client: TestClient,
    make_user: Callable[..., User],
    make_tenant: Callable[..., Tenant],
) -> None:
    window = {**_range(60, 30), "dry_run": True}
    assert user_client.post("/api/v1/audit/purge", json=window).status_code == 403

    other = make_tenant("otra")
    make_user("jefa", role="admin", tenant_id=other.id)  # administradora de su tenant, no de la instancia
    tenant_admin = login_as(user_client, "jefa")
    assert tenant_admin.get("/api/v1/audit").status_code == 200  # ve la auditoría de su tenant…
    assert tenant_admin.post("/api/v1/audit/purge", json=window).status_code == 403  # …pero no la borra
