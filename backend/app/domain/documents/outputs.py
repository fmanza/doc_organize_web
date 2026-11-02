"""Ruta de las salidas de un documento convertido, sin importar doc_organize (G20).

``DocumentConverter.resolve_output_paths`` y ``resolve_images_dir`` viven en un módulo de doc_organize que importa
Docling, así que la API (que no carga Docling, G15) replica aquí la misma regla, verificada en el tag ``v0.11.0`` y
comprobada por ``tests/integration/test_documents_contract.py``:

- la salida replica la ruta del documento **relativa a la carpeta escaneada** bajo ``Conversión/<carpeta>/``;
- cada carpeta intermedia y el nombre sin extensión pierden los espacios y puntos finales (``rstrip(" .")``);
- Markdown ``<stem>.md``, JSON ``<stem>.json`` e imágenes en ``img/<stem>/`` junto al Markdown.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(frozen=True)
class OutputPaths:
    """Salidas de un documento, relativas a la carpeta ``Conversión/`` del proyecto (con ``/``).

    Attributes:
        markdown: ``<carpeta>/<ruta>/<stem>.md``.
        json: ``<carpeta>/<ruta>/<stem>.json``.
        images: ``<carpeta>/<ruta>/img/<stem>`` (puede no existir).
    """

    markdown: str
    json: str
    images: str


def output_paths(folder: str, relative: str) -> OutputPaths:
    """Salidas del documento ``relative`` (ruta dentro de la carpeta de origen ``folder``; ``""`` = la raíz).

    Example:
        >>> output_paths("2024", "facturas/enero .pdf").markdown
        '2024/facturas/enero.md'
    """
    parts = PurePosixPath(relative).parts
    stem = PurePosixPath(parts[-1]).stem.rstrip(" .") if parts else ""
    target = PurePosixPath(folder, *(part.rstrip(" .") for part in parts[:-1]))
    prefix = "" if str(target) == "." else f"{target.as_posix()}/"
    return OutputPaths(markdown=f"{prefix}{stem}.md", json=f"{prefix}{stem}.json", images=f"{prefix}img/{stem}")
