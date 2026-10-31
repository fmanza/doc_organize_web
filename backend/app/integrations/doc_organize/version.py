"""Versión instalada de doc_organize."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version


def library_version() -> str | None:
    """Versión de doc_organize según los metadatos del paquete, o None si no está instalado.

    Se leen los metadatos y no ``doc_organize.__version__``: hasta la 0.9.3 ese atributo no coincidía con la versión
    real (G1), e importar el paquete cargaría Docling solo para leer un número.
    """
    try:
        return version("doc_organize")
    except PackageNotFoundError:
        return None
