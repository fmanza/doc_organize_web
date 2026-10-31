"""Fixtures comunes: ajustes aislados en ``tmp_path``, ``config.db`` migrada, cliente HTTPS y usuarios."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.db.models import Role, User
from app.db.session import get_engine
from app.domain.identity.audit import CLI_CONTEXT
from app.domain.identity.users import create_user
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
    def _make(username: str, password: str = USER_PASSWORD, role: Role = "user") -> User:
        return create_user(
            db,
            username=username,
            display_name=username.title(),
            password=password,
            role=role,
            settings=migrated,
            ctx=CLI_CONTEXT,
            actor_id=None,
        )

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
