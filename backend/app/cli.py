"""Comandos de administración.

Uso::

    python -m app.cli create-admin --username admin [--display-name "Administración"] [--password-stdin]
    python -m app.cli backup [--dest /data/backups] [--keep 7]
    python -m app.cli verify-backup /data/backups/20261102T030000Z
    python -m app.cli rotate-secrets

``rotate-secrets`` vuelve a cifrar las credenciales de IA con la primera clave de ``DOW_FERNET_KEYS`` (ADR-004): se
antepone la clave nueva, se ejecuta y, después, se puede retirar la antigua.

Sin ``--password-stdin`` la contraseña se pide dos veces por terminal (``getpass``). En Docker::

    docker compose exec web python -m app.cli create-admin --username admin
"""

from __future__ import annotations

import argparse
import getpass
import logging
import sqlite3
import sys
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from app.core import crypto
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import configure_logging
from app.db import backup
from app.db.session import get_engine
from app.domain.ai import settings as ai_settings
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


def run_backup(destination: str | None, keep: int | None) -> int:
    """Copia ``config.db`` y las cachés; devuelve el código de salida."""
    if keep is not None and keep < 1:
        print("Error: --keep debe ser 1 o más (la copia nueva siempre se conserva).", file=sys.stderr)
        return 2
    try:
        target = backup.create_backup(get_settings(), destination=Path(destination) if destination else None, keep=keep)
    except FileExistsError:
        print("Error: ya hay una copia de este mismo segundo; vuelve a intentarlo.", file=sys.stderr)
        return 1
    except (OSError, sqlite3.Error) as exc:
        print(f"Error: no se pudo hacer la copia ({type(exc).__name__}).", file=sys.stderr)
        return 1
    problems = backup.verify_backup(target)
    for problem in problems:
        print(f"Error: {problem}", file=sys.stderr)
    if problems:
        return 1
    print(f"Copia creada en {target}.")
    return 0


def run_verify(path: str) -> int:
    """Comprueba una copia; devuelve el código de salida."""
    problems = backup.verify_backup(Path(path))
    for problem in problems:
        print(f"Error: {problem}", file=sys.stderr)
    if not problems:
        print("La copia es correcta.")
    return 1 if problems else 0


def run_rotate() -> int:
    """Vuelve a cifrar las credenciales de IA con la primera clave; devuelve el código de salida."""
    session_factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    with session_factory() as db:
        try:
            result = ai_settings.rotate_all(db, get_settings())
        except crypto.EncryptionNotConfiguredError:
            print("Error: DOW_FERNET_KEYS no está definida o no tiene claves Fernet válidas.", file=sys.stderr)
            return 1
    print(f"Credenciales vueltas a cifrar: {result.rotated}.")
    if result.failed:
        print(
            f"Error: {result.failed} credenciales no se descifran con ninguna clave; hay que volver a introducirlas.",
            file=sys.stderr,
        )
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Administración de doc_organize_web")
    commands = parser.add_subparsers(dest="command", required=True)
    admin = commands.add_parser("create-admin", help="crea un usuario administrador")
    admin.add_argument("--username", required=True)
    admin.add_argument("--display-name")
    admin.add_argument("--password-stdin", action="store_true", help="lee la contraseña de la entrada estándar")
    copy = commands.add_parser("backup", help="copia config.db y las cachés de doc_organize")
    copy.add_argument("--dest", help="carpeta de las copias (por defecto /data/backups)")
    copy.add_argument("--keep", type=int, help="copias que se conservan en la carpeta (borra las más antiguas)")
    verify = commands.add_parser("verify-backup", help="comprueba una copia (hashes e integridad de SQLite)")
    verify.add_argument("path", help="carpeta de la copia")
    commands.add_parser("rotate-secrets", help="vuelve a cifrar las credenciales de IA con la primera clave")
    args = parser.parse_args(argv)

    configure_logging(get_settings().log_level)
    if args.command == "create-admin":
        return create_admin(args.username, args.display_name, password_stdin=args.password_stdin)
    if args.command == "backup":
        return run_backup(args.dest, args.keep)
    if args.command == "verify-backup":
        return run_verify(args.path)
    if args.command == "rotate-secrets":
        return run_rotate()
    return 2  # pragma: no cover - argparse exige un comando


if __name__ == "__main__":
    raise SystemExit(main())
