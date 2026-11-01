"""Reglas de carpetas de un proyecto que no dependen de la BD: nombre de una carpeta nueva y solapes de rutas.

El nombre se valida con reglas portables propias (Linux, SMB y NFS montados desde Windows): la API no importa
doc_organize (G15) y la carpeta no lleva el nombre del proyecto, así que no se usa ``ProjectValidator``.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import PurePosixPath
from typing import Final

MAX_FOLDER_NAME = 120
_FORBIDDEN: Final = re.compile(r'[<>:"/\\|?*\x00-\x1f\x7f]')
_RESERVED: Final = re.compile(r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?$", re.IGNORECASE)


def folder_name_problem(name: str) -> str | None:
    """Motivo por el que ``name`` no sirve como nombre de carpeta nueva, o ``None`` si es válido."""
    if not name.strip():
        return "El nombre de la carpeta no puede estar vacío."
    if name != name.strip():
        return "El nombre de la carpeta no puede empezar ni terminar en espacio."
    if len(name) > MAX_FOLDER_NAME:
        return f"El nombre de la carpeta no puede superar {MAX_FOLDER_NAME} caracteres."
    if unicodedata.normalize("NFC", name) != name:
        return "El nombre de la carpeta debe estar en forma Unicode normalizada (NFC)."
    if set(name) == {"."} or name.endswith("."):
        return "El nombre de la carpeta no puede terminar en punto."
    if _FORBIDDEN.search(name):
        return 'El nombre de la carpeta no puede contener < > : " / \\ | ? * ni caracteres de control.'
    if _RESERVED.match(name):
        return "El nombre de la carpeta coincide con un nombre reservado (CON, PRN, AUX, NUL, COM1-9, LPT1-9)."
    return None


def nested(a: str, b: str) -> bool:
    """Si dos rutas relativas normalizadas de la misma raíz son iguales o una contiene a la otra (``""`` = raíz)."""
    pa, pb = PurePosixPath(a or "."), PurePosixPath(b or ".")
    return pa == pb or not a or not b or pa.is_relative_to(pb) or pb.is_relative_to(pa)


def nested_pair(paths: list[str]) -> tuple[str, str] | None:
    """Primer par de rutas distintas de ``paths`` en el que una contiene a la otra, o ``None``."""
    unique = sorted(set(paths), key=lambda p: (p.count("/"), p))
    for i, outer in enumerate(unique):
        for inner in unique[i + 1 :]:
            if nested(outer, inner):
                return outer, inner
    return None
