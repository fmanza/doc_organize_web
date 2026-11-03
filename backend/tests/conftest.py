"""Fixtures comunes: ajustes aislados en ``tmp_path``, ``config.db`` migrada, cliente HTTPS y usuarios."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Literal

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.db.models import DEFAULT_TENANT_ID, Location, Tenant, User
from app.db.session import get_engine
from app.domain.identity.audit import CLI_CONTEXT
from app.domain.identity.users import create_user
from app.domain.locations.service import create_location
from app.domain.tenancy.roles import builtin_role, create_builtin_roles
from app.main import create_app

BACKEND_DIR = Path(__file__).resolve().parents[1]
ADMIN_PASSWORD = "admin-password-1234"
USER_PASSWORD = "user-password-1234"

LoginFn = Callable[[TestClient, str, str], None]


@pytest.fixture
def settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Settings]:
    """Ajustes con carpetas temporales; limpia las cachés de proceso."""
    monkeypatch.setenv("DOW_ENVIRONMENT", "test")
    for name in ("data", "workspace", "static"):
        monkeypatch.setenv(f"DOW_{name.upper()}_DIR", str(tmp_path / name))
    monkeypatch.setenv("DOW_LOCATIONS_ROOT", str(tmp_path / "mnt"))
    get_settings.cache_clear()
    get_engine.cache_clear()
    yield get_settings()
    get_engine().dispose()
    get_settings.cache_clear()
    get_engine.cache_clear()


def run_migrations(revision: str = "head") -> None:
    """Aplica Alembic sobre la ``config.db`` de los ajustes actuales."""
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(config, revision)


@pytest.fixture
def migrated(settings: Settings) -> Settings:
    run_migrations()
    return settings


@pytest.fixture
def db(migrated: Settings) -> Iterator[Session]:
    with sessionmaker(bind=get_engine(), expire_on_commit=False)() as session:
        yield session


@pytest.fixture
def client(migrated: Settings) -> Iterator[TestClient]:
    # HTTPS: las cookies llevan ``Secure`` fuera de ``development``.
    with TestClient(create_app(migrated), base_url="https://testserver") as test_client:
        yield test_client


@pytest.fixture
def make_user(db: Session, migrated: Settings) -> Callable[..., User]:
    """Usuario del tenant ``tenant_id`` con un rol base: ``admin`` es además admin de instancia en ``default`` (como
    los ``admin`` migrados, decisión E4) y solo «Administrador» del tenant en otro; ``user``, «Usuario»."""

    def _make(
        username: str,
        password: str = USER_PASSWORD,
        role: Literal["admin", "user"] = "user",
        *,
        tenant_id: int = DEFAULT_TENANT_ID,
        instance_admin: bool | None = None,
    ) -> User:
        return create_user(
            db,
            username=username,
            display_name=username.title(),
            password=password,
            settings=migrated,
            ctx=CLI_CONTEXT,
            actor=None,
            tenant_id=tenant_id,
            role_id=builtin_role(db, tenant_id, role).id,
            is_instance_admin=(role == "admin" and tenant_id == DEFAULT_TENANT_ID)
            if instance_admin is None
            else instance_admin,
        )

    return _make


@pytest.fixture
def make_tenant(db: Session, migrated: Settings) -> Callable[..., Tenant]:
    """Tenant nuevo con sus roles base (como ``POST /tenants``)."""

    def _make(slug: str, name: str | None = None) -> Tenant:
        tenant = Tenant(slug=slug, name=name or slug.title())
        db.add(tenant)
        db.flush()
        create_builtin_roles(db, tenant.id)
        db.commit()
        return tenant

    return _make


@pytest.fixture
def admin(make_user: Callable[..., User]) -> User:
    return make_user("admin", ADMIN_PASSWORD, "admin")


@pytest.fixture
def user(make_user: Callable[..., User]) -> User:
    return make_user("ana", USER_PASSWORD, "user")


def do_login(client: TestClient, username: str, password: str) -> None:
    """Obtiene CSRF, inicia sesión y deja la cabecera ``X-CSRF-Token`` puesta en el cliente."""
    csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    response = client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}, headers={"X-CSRF-Token": csrf}
    )
    assert response.status_code == 200, response.text
    client.headers["X-CSRF-Token"] = client.cookies[get_settings().csrf_cookie]


@pytest.fixture
def admin_client(client: TestClient, admin: User) -> TestClient:
    do_login(client, admin.username, ADMIN_PASSWORD)
    return client


@pytest.fixture
def user_client(client: TestClient, user: User) -> TestClient:
    do_login(client, user.username, USER_PASSWORD)
    return client


def login_as(client: TestClient, username: str, password: str = USER_PASSWORD) -> TestClient:
    """Otro cliente sobre la misma aplicación con la sesión de ``username``."""
    other = TestClient(client.app, base_url="https://testserver")
    do_login(other, username, password)
    return other


@pytest.fixture
def project_locations(db: Session, migrated: Settings, admin: User) -> dict[str, Location]:
    """Ubicación de origen ``ro`` (``origen/{2024,2025}``) y de destino ``rw`` (``salidas``) bajo la raíz."""
    root = migrated.locations_root
    (root / "origen" / "2024").mkdir(parents=True)
    (root / "origen" / "2025").mkdir()
    (root / "origen" / "2024" / "factura.txt").write_text("documento sintético", encoding="utf-8")
    (root / "salidas").mkdir()
    common = {
        "display_path": None,
        "kind": "local",
        "settings": migrated,
        "actor": admin,
        "ctx": CLI_CONTEXT,
        "tenant_id": DEFAULT_TENANT_ID,
    }
    source = create_location(db, name="Origen", path="origen", usage="source", access="ro", **common)  # type: ignore[arg-type]
    destination = create_location(db, name="Salidas", path="salidas", usage="destination", access="rw", **common)  # type: ignore[arg-type]
    return {"source": source, "destination": destination}


def project_payload(locations: dict[str, Location], name: str = "Proyecto A", **extra: object) -> dict[str, object]:
    """Cuerpo de ``POST /projects`` con carpeta de salidas nueva ``name``."""
    return {
        "name": name,
        "source_location_id": locations["source"].id,
        "source_subpaths": ["2024"],
        "destination_location_id": locations["destination"].id,
        "destination_parent": "",
        "new_folder": name,
        **extra,
    }
