"""Comandos de administración.

Uso::

    python -m app.cli create-admin --username admin [--display-name "Administración"] [--password-stdin]

Sin ``--password-stdin`` la contraseña se pide dos veces por terminal (``getpass``). En Docker::

    docker compose exec web python -m app.cli create-admin --username admin
"""

from __future__ import annotations

import argparse
import getpass
import logging
import sys

from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import configure_logging
from app.db.session import get_engine
from app.domain.identity.audit import CLI_CONTEXT
from app.domain.identity.users import create_user
from app.domain.settings.service import effective_settings

logger = logging.getLogger(__name__)


def _read_password(from_stdin: bool) -> str:
    if from_stdin:
        return sys.stdin.readline().rstrip("\r\n")
    first = getpass.getpass("Contraseña: ")
    if getpass.getpass("Repite la contraseña: ") != first:
        raise SystemExit("Las contraseñas no coinciden.")
    return first


def create_admin(username: str, display_name: str | None, *, password_stdin: bool) -> int:
    """Crea un usuario ``admin``; devuelve el código de salida."""
    password = _read_password(password_stdin)
    factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    with factory() as db:
        settings = effective_settings(db, get_settings())
        try:
            user = create_user(
                db,
                username=username,
                display_name=display_name or username,
                password=password,
                role="admin",
                settings=settings,
                ctx=CLI_CONTEXT,
                actor_id=None,
            )
        except AppError as exc:
            print(f"Error: {exc.title}. {exc.detail or ''}".strip(), file=sys.stderr)
            return 1
    print(f"Administrador «{user.username}» creado (id {user.id}).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Administración de doc_organize_web")
    commands = parser.add_subparsers(dest="command", required=True)
    admin = commands.add_parser("create-admin", help="crea un usuario administrador")
    admin.add_argument("--username", required=True)
    admin.add_argument("--display-name")
    admin.add_argument("--password-stdin", action="store_true", help="lee la contraseña de la entrada estándar")
    args = parser.parse_args(argv)

    configure_logging(get_settings().log_level)
    if args.command == "create-admin":
        return create_admin(args.username, args.display_name, password_stdin=args.password_stdin)
    return 2  # pragma: no cover - argparse exige un comando


if __name__ == "__main__":
    raise SystemExit(main())
