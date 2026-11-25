"""Web 2.7 (ADR-017): lo excluido que sigue en la caché no entra en el contexto (``SourceFolder.skip``)."""

from __future__ import annotations

from pathlib import Path

from app.integrations.doc_organize.context import SourceFolder, converted_documents
from tests.api.test_documents import entry, write_cache


def test_skipped_entries_are_left_out_before_checking_their_outputs(tmp_path: Path) -> None:
    root = tmp_path / "origen" / "2024"
    (root / "fotos").mkdir(parents=True)
    cache = tmp_path / "state" / "cache.db"
    write_cache(cache, [entry(root / "acta.txt"), entry(root / "fotos" / "foto.txt")])

    def folder(skip: object = None) -> SourceFolder:
        return SourceFolder(
            folder="2024",
            root=root,
            cache_db=cache,
            conversion_dir=tmp_path / "Conversión" / "2024",
            skip=skip,  # type: ignore[arg-type]
        )

    # Sin salidas convertidas, las dos cuentan como incompletas; la excluida ni siquiera se mira.
    assert converted_documents([folder()]) == ([], 2)
    assert converted_documents([folder(lambda path: "fotos" in Path(path).parts)]) == ([], 1)
