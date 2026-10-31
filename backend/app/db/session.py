"""Engine de SQLite con los PRAGMA de ADR-001 y fábrica de sesiones.

Los PRAGMA solo se aplican en el *listener* de conexión y solo si el motor es SQLite: cambiar a otra BD es cambiar la
URL y el driver (D8).
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache
from typing import Any

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

SQLITE_PRAGMAS: tuple[str, ...] = (
    "PRAGMA journal_mode=WAL",
    "PRAGMA synchronous=NORMAL",
    "PRAGMA busy_timeout=5000",
    "PRAGMA foreign_keys=ON",
)


def build_engine(url: str) -> Engine:
    """Engine SQLAlchemy; con SQLite aplica los PRAGMA en cada conexión nueva."""
    is_sqlite = url.startswith("sqlite")
    engine = create_engine(url, connect_args={"check_same_thread": False} if is_sqlite else {})

    if is_sqlite:

        @event.listens_for(engine, "connect")
        def _set_pragmas(dbapi_connection: Any, _: Any) -> None:
            cursor = dbapi_connection.cursor()
            for pragma in SQLITE_PRAGMAS:
                cursor.execute(pragma)
            cursor.close()

    return engine


@lru_cache
def get_engine() -> Engine:
    """Engine del proceso sobre ``config.db``; crea ``data_dir`` si no existe."""
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return build_engine(settings.database_url)


def get_session() -> Iterator[Session]:
    """Dependencia FastAPI: una sesión por petición."""
    factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    with factory() as session:
        yield session


def ping(engine: Engine) -> bool:
    """True si la base de datos responde a ``SELECT 1``."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError):
        return False
    return True
