"""Ruta de las salidas de un documento convertido.

La regla (ruta relativa a la carpeta escaneada bajo ``Conversión/<carpeta>/``, ``rstrip(" .")`` de cada segmento,
``<stem>.md``/``<stem>.json`` e imágenes en ``img/<stem>/``) es la de doc_organize: desde 0.12.0
``resolve_output_paths`` y ``resolve_images_dir`` viven en ``doc_organize.projects.layout``, sin Docling (G20), y la API
las usa a través de la capa anticorrupción.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.integrations.doc_organize import cache as library_cache


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
    markdown, json_path, images = library_cache.output_paths(folder, relative)
    return OutputPaths(markdown=markdown, json=json_path, images=images)
