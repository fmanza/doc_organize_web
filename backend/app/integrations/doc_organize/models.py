"""Modelos de Docling sin Internet (ADR-011): descarga a ``DOW_MODELS_DIR`` y estado para las capacidades.

La descarga la hace un servicio puntual (``models-init`` en compose) con este módulo como programa::

    python -m app.integrations.doc_organize.models download [--picture-description] [--easyocr]

Al terminar escribe ``manifest.json``; el estado se lee de ese fichero (y de que existan las carpetas), sin importar
Docling. Los jobs apuntan Docling a la carpeta con ``DOCLING_ARTIFACTS_PATH`` (verificado en docling 2.142:
``AppSettings`` con prefijo ``DOCLING_``) y el worker corre con ``HF_HUB_OFFLINE=1``.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

DOCLING_SUBDIR: Final = "docling"
MANIFEST: Final = "manifest.json"


@dataclass(frozen=True)
class ModelsStatus:
    """Modelos presentes en la carpeta de modelos.

    Attributes:
        ready: Modelos base (*layout*, tablas, RapidOCR): sin ellos los PDF y las imágenes no se convierten.
        picture_description: Modelo de visión (SmolVLM) para describir imágenes.
        easyocr: Modelos de EasyOCR, el motor de OCR con GPU.
    """

    ready: bool = False
    picture_description: bool = False
    easyocr: bool = False


def docling_dir(models_dir: Path) -> Path:
    """Carpeta de artefactos de Docling dentro de la carpeta de modelos."""
    return models_dir / DOCLING_SUBDIR


def status(models_dir: Path) -> ModelsStatus:
    """Estado según ``manifest.json`` y las carpetas que nombra (no importa Docling)."""
    root = docling_dir(models_dir)
    try:
        manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ModelsStatus()
    folders = manifest.get("folders") or {}

    def present(key: str) -> bool:
        names = folders.get(key) or []
        return bool(names) and all((root / name).is_dir() for name in names)

    return ModelsStatus(
        ready=present("base"), picture_description=present("picture_description"), easyocr=present("easyocr")
    )


def merge_folders(root: Path, downloaded: dict[str, list[str]]) -> dict[str, list[str]]:
    """Carpetas del nuevo manifiesto: las descargadas ahora más los grupos opcionales de antes que sigan en disco.

    Así ``models-init`` (CPU) y ``models-init-gpu`` (EasyOCR) no se borran del manifiesto el uno al otro.
    """
    try:
        previous = json.loads((root / MANIFEST).read_text(encoding="utf-8")).get("folders") or {}
    except (OSError, ValueError, AttributeError):
        previous = {}
    merged = dict(downloaded)
    for group, names in downloaded.items():
        kept = previous.get(group) or []
        if not names and kept and all((root / name).is_dir() for name in kept):
            merged[group] = list(kept)
    return merged


def configure(models_dir: Path) -> None:
    """Apunta Docling a la carpeta de modelos, si se descargaron. Llamar antes de importar doc_organize o Docling."""
    root = docling_dir(models_dir)
    if (root / MANIFEST).is_file():
        os.environ["DOCLING_ARTIFACTS_PATH"] = str(root)


def download(models_dir: Path, *, picture_description: bool = False, easyocr: bool = False) -> ModelsStatus:
    """Descarga los modelos con ``docling.utils.model_downloader.download_models`` y escribe el manifiesto."""
    from docling.models.stages.table_structure.table_structure_model import TableStructureModel
    from docling.utils.model_downloader import download_models

    root = docling_dir(models_dir)
    root.mkdir(parents=True, exist_ok=True)
    download_models(output_dir=root, progress=True, with_smolvlm=False, with_easyocr=False)
    base = sorted({p.name for p in root.iterdir() if p.is_dir()} | {TableStructureModel._model_repo_folder})
    folders: dict[str, list[str]] = {"base": base, "picture_description": [], "easyocr": []}
    if picture_description:
        from docling.datamodel.pipeline_options import smolvlm_picture_description

        download_models(
            output_dir=root, with_layout=False, with_tableformer=False, with_code_formula=False,
            with_picture_classifier=False, with_rapidocr=False, with_smolvlm=True,
        )  # fmt: skip
        folders["picture_description"] = [smolvlm_picture_description.repo_cache_folder]
    if easyocr:
        from docling.models.stages.ocr.easyocr_model import EasyOcrModel

        download_models(
            output_dir=root, with_layout=False, with_tableformer=False, with_code_formula=False,
            with_picture_classifier=False, with_rapidocr=False, with_easyocr=True,
        )  # fmt: skip
        folders["easyocr"] = [EasyOcrModel._model_repo_folder]
    manifest = {"downloaded_at": datetime.now(UTC).isoformat(), "folders": merge_folders(root, folders)}
    (root / MANIFEST).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return status(models_dir)


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - programa del servicio models-init
    """Punto de entrada: ``download`` con los modelos opcionales que se pidan."""
    parser = argparse.ArgumentParser(prog="python -m app.integrations.doc_organize.models")
    sub = parser.add_subparsers(dest="command", required=True)
    dl = sub.add_parser("download", help="Descarga los modelos de Docling a DOW_MODELS_DIR")
    dl.add_argument("--picture-description", action="store_true", help="También el modelo de visión (SmolVLM)")
    dl.add_argument("--easyocr", action="store_true", help="También EasyOCR (OCR con GPU)")
    args = parser.parse_args(argv)
    # Sin los ajustes de la aplicación: `models-init` corre sin secretos ni `config.db` (solo el volumen de modelos).
    models_dir = Path(os.environ.get("DOW_MODELS_DIR", "/models"))
    result = download(models_dir, picture_description=args.picture_description, easyocr=args.easyocr)
    print(json.dumps(asdict(result)))
    return 0 if result.ready else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
