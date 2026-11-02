"""Dónde vive el estado de doc_organize de cada carpeta de origen (Fase 4) y dónde quedan sus salidas.

Cada carpeta de origen es un ámbito propio: caché e historiales en ``/data/projects/<id>/folders/<clave>/`` y
conversiones en ``<salidas>/Conversión/<carpeta>/`` (G18). Lo usan el worker (escaneo, exportaciones, índice) y la API
(listado de documentos, visor).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Final

FOLDERS_STATE_DIR: Final = "folders"
#: ``ProjectLayout.conversion_dir`` de doc_organize (``CONVERSION_FOLDER_NAME``); lo comprueba un test de contrato.
CONVERSION_DIR: Final = "Conversión"
#: ``ProjectLayout.cache_db`` relativo a su ``state_root``; lo comprueba un test de contrato.
CACHE_DB: Final = "cache.db"


def folder_state(project_state: Path, subpath: str) -> Path:
    """Carpeta de estado de una carpeta de origen: clave estable derivada de su ruta relativa (sin caracteres raros)."""
    return project_state / FOLDERS_STATE_DIR / hashlib.sha256(subpath.encode("utf-8")).hexdigest()[:16]


def folder_cache(project_state: Path, subpath: str) -> Path:
    """``cache.db`` de doc_organize de una carpeta de origen."""
    return folder_state(project_state, subpath) / CACHE_DB
