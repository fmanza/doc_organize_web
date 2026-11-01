"""Carpeta de cada run en el volumen ``workspace`` (ADR-005): ``run.json``, ``logs/run.log`` y ``outputs/``.

Las rutas se construyen **solo con el UUID del run** y las de artefactos se comprueban con ``resolve()`` +
``is_relative_to``: nada que llegue del usuario forma parte de una ruta.
"""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Any

from app.core.config import Settings

RUN_JSON = "run.json"
LOG_REL = "logs/run.log"
OUTPUTS = "outputs"


def run_dir(settings: Settings, run_id: str) -> Path:
    """Carpeta del run; ``run_id`` debe ser un UUID (se normaliza).

    Raises:
        ValueError: ``run_id`` no es un UUID.
    """
    return settings.workspace_dir / "runs" / str(uuid.UUID(run_id))


def ensure(settings: Settings, run_id: str) -> Path:
    """Crea ``logs/`` y ``outputs/`` del run y devuelve su carpeta."""
    base = run_dir(settings, run_id)
    (base / "logs").mkdir(parents=True, exist_ok=True)
    (base / OUTPUTS).mkdir(exist_ok=True)
    return base


def write_run_json(settings: Settings, run_id: str, data: dict[str, Any]) -> None:
    """Escribe ``run.json`` (operación, parámetros, estado y tiempos; nunca secretos ni rutas del contenedor)."""
    base = ensure(settings, run_id)
    tmp = base / f".{RUN_JSON}.tmp"
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    tmp.replace(base / RUN_JSON)


def artifact_path(settings: Settings, run_id: str, rel_path: str) -> Path | None:
    """Ruta de un artefacto si existe y queda dentro de la carpeta del run; ``None`` si no."""
    base = run_dir(settings, run_id).resolve()
    try:
        path = (base / rel_path).resolve(strict=True)
    except OSError:
        return None
    if not path.is_relative_to(base) or not path.is_file():
        return None
    return path


def purge(settings: Settings, run_id: str) -> None:
    """Borra la carpeta del run (retención); no falla si ya no existe."""
    shutil.rmtree(run_dir(settings, run_id), ignore_errors=True)
