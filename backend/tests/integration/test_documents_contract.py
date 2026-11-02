"""Contrato de G20: ``output_paths`` de la web da las mismas rutas que ``DocumentConverter.resolve_output_paths`` y
``resolve_images_dir`` de doc_organize (que importan Docling, por eso este test está fuera del CI:
``pytest -m integration``)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.domain.documents.outputs import output_paths

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "relative",
    ["factura.pdf", "facturas /enero. .pdf", "a/b/c.docx", "x.tar.gz", "Café y té/acta 1.html", "sin_extension"],
)
def test_output_paths_match_doc_organize(tmp_path: Path, relative: str) -> None:
    from doc_organize.converter.converter import DocumentConverter

    folder = tmp_path / "origen" / "2024"
    conversion = tmp_path / "Conversión"
    markdown, json_path = DocumentConverter.resolve_output_paths(
        str(folder / relative), conversion / "2024", [str(folder)]
    )
    images = DocumentConverter.resolve_images_dir(markdown)
    ours = output_paths("2024", relative)

    assert markdown.relative_to(conversion).as_posix() == ours.markdown
    assert json_path.relative_to(conversion).as_posix() == ours.json
    assert images.relative_to(conversion).as_posix() == ours.images
