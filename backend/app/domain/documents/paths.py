"""Rutas de documentos tal como las ve el usuario: relativas a su carpeta de origen, nunca del contenedor.

La caché de doc_organize guarda la ruta **absoluta** de cada documento (``/mnt/…/2024/facturas/a.pdf``). Antes de
devolverla por la API o escribirla en una exportación se convierte en ``(carpeta, ruta relativa)`` con las raíces de
las carpetas de origen; los mensajes de error pasan por ``PathRedactor``.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path, PurePosixPath

from app.core.redact import PathRedactor
from app.domain.locations.errors import LocationUnavailableError
from app.domain.locations.paths import run_with_timeout


def folder_roots(container_path: str, subpath: str, *, timeout: float) -> list[Path]:
    """Raíces posibles de una carpeta de origen: la ruta registrada y la resuelta (si un enlace cambia la ruta).

    doc_organize guarda las rutas que recibió (la resuelta, en el escaneo). Si la ubicación no responde, solo se usa la
    registrada: nunca se bloquea la petición.
    """
    registered = Path(container_path) / subpath if subpath else Path(container_path)
    roots = [registered]
    try:
        resolved = Path(run_with_timeout(lambda: os.path.realpath(registered), timeout))
    except LocationUnavailableError:
        return roots
    if resolved != registered:
        roots.append(resolved)
    return roots


class DocumentNamer:
    """Convierte rutas absolutas de documentos en ``(carpeta, relativa)`` y limpia rutas de los mensajes.

    Args:
        folders: ``(subpath de la carpeta, raíces absolutas)`` de cada carpeta de origen.
        location: Nombre de la ubicación de origen (etiqueta de las rutas que queden en los mensajes).
    """

    def __init__(self, folders: Iterable[tuple[str, Iterable[Path]]], location: str) -> None:
        pairs = [(str(root).rstrip("/"), subpath) for subpath, roots in folders for root in roots]
        # Las raíces más largas primero: una ruta se atribuye a la carpeta más concreta.
        self._roots = sorted(pairs, key=lambda pair: -len(pair[0]))
        self._redactor = PathRedactor(
            (root, f"«{location}»/{subpath}" if subpath else f"«{location}»") for root, subpath in self._roots
        )

    def split(self, path: str) -> tuple[str, str] | None:
        """``(carpeta, ruta relativa a ella)`` o ``None`` si ``path`` no está bajo ninguna carpeta."""
        for root, subpath in self._roots:
            if path.startswith(root + "/"):
                return subpath, PurePosixPath(path[len(root) + 1 :]).as_posix()
        return None

    def display(self, path: str) -> str:
        """``<carpeta>/<relativa>``; si no está bajo ninguna carpeta, solo el nombre del fichero."""
        parts = self.split(path)
        if parts is None:
            return PurePosixPath(path.replace("\\", "/")).name
        subpath, relative = parts
        return f"{subpath}/{relative}" if subpath else relative

    def text(self, message: str) -> str:
        """``message`` sin rutas del contenedor."""
        return self._redactor.text(message)
