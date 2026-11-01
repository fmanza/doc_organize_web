"""Conversión real con doc_organize 0.10.0 y Docling (fuera del CI: ``pytest -m integration``).

Documentos sintéticos generados por el test: un HTML (sin modelos) y un PDF de una imagen hecho con Pillow ≥ 13
(requisito de seguridad de la Fase 4; necesita los modelos de Docling, en ``DOW_MODELS_DIR`` o descargables). Comprueba
también que el segundo escaneo es incremental (0 conversiones) y que una cancelación previa no convierte nada.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from app.integrations.doc_organize import ScanProgress, ScanRequest, run_scan

pytestmark = pytest.mark.integration


def _documents(source: Path) -> None:
    source.mkdir(parents=True)
    (source / "nota.html").write_text(
        "<html><body><h1>Nota sintética</h1><p>Texto de prueba para la conversión.</p></body></html>",
        encoding="utf-8",
    )
    image = Image.new("RGB", (800, 300), "white")
    ImageDraw.Draw(image).text((40, 120), "FACTURA SINTETICA 2026", fill="black")
    image.save(source / "factura.pdf", "PDF", resolution=100)


def _request(tmp_path: Path, models_dir: Path, **options: bool) -> ScanRequest:
    return ScanRequest(
        folders=[tmp_path / "origen"],
        output_root=tmp_path / "salidas",
        state_root=tmp_path / "estado",
        models_dir=models_dir,
        **options,
    )


@pytest.fixture
def models_dir() -> Path:
    import os

    return Path(os.environ.get("DOW_MODELS_DIR", "/models"))


def test_real_scan_is_incremental(tmp_path: Path, models_dir: Path) -> None:
    _documents(tmp_path / "origen")
    (tmp_path / "salidas").mkdir()
    progress: list[ScanProgress] = []

    first = run_scan(
        _request(tmp_path, models_dir, use_ocr=False), on_progress=progress.append, is_cancelled=lambda: False
    )
    second = run_scan(
        _request(tmp_path, models_dir, use_ocr=False), on_progress=progress.append, is_cancelled=lambda: False
    )

    assert not first.cancelled and first.summary["scanned"] == 2
    assert first.summary["converted"] + first.summary["conversion_errors"] == 2
    assert any((tmp_path / "salidas").rglob("nota.md")) and any((tmp_path / "salidas").rglob("factura.md"))
    assert second.summary["converted"] == 0 and second.summary["unchanged"] == 2
    assert {p.phase for p in progress} >= {"conversion", "done"}
    assert any((tmp_path / "estado").rglob("*.db"))
    assert len(first.reports) == 1 and first.reports[0]["completed"] is True


def test_cancel_stops_between_documents_and_keeps_the_cache(tmp_path: Path, models_dir: Path) -> None:
    source = tmp_path / "origen"
    source.mkdir()
    for i in range(20):
        (source / f"nota{i:02d}.html").write_text(f"<html><body><p>Nota {i}</p></body></html>", encoding="utf-8")
    (tmp_path / "salidas").mkdir()
    converted: list[str] = []

    def on_progress(event: ScanProgress) -> None:
        if event.phase == "conversion" and event.processed > len(converted):
            converted.append(event.current or "")

    stopped = run_scan(
        _request(tmp_path, models_dir, use_ocr=False), on_progress=on_progress, is_cancelled=lambda: bool(converted)
    )
    resumed = run_scan(
        _request(tmp_path, models_dir, use_ocr=False), on_progress=lambda _: None, is_cancelled=lambda: False
    )

    assert stopped.cancelled and 1 <= stopped.summary["converted"] < 20
    assert stopped.reports[0]["completed"] is False
    # Lo convertido antes de parar quedó en la caché: el siguiente escaneo solo convierte el resto.
    assert resumed.summary["converted"] == 20 - stopped.summary["converted"]


def test_same_relative_name_in_two_folders_does_not_collide(tmp_path: Path, models_dir: Path) -> None:
    """doc_organize deriva la salida sin el nombre de la carpeta escaneada (G18): la web da a cada carpeta su ámbito."""
    for year in ("2024", "2025"):
        folder = tmp_path / "origen" / year / "facturas"
        folder.mkdir(parents=True)
        (folder / "enero.html").write_text(f"<html><body><p>Factura {year}</p></body></html>", encoding="utf-8")
    (tmp_path / "salidas").mkdir()

    for year in ("2024", "2025"):
        request = ScanRequest(
            folders=[tmp_path / "origen" / year],
            output_root=tmp_path / "salidas",
            state_root=tmp_path / "estado" / year,
            models_dir=models_dir,
            output_subdir=year,
            use_ocr=False,
        )
        assert run_scan(request, on_progress=lambda _: None, is_cancelled=lambda: False).summary["converted"] == 1

    outputs = sorted(p for p in (tmp_path / "salidas").rglob("enero.md"))
    assert len(outputs) == 2
    assert {p.parent.parent.name for p in outputs} == {"2024", "2025"}
    assert {p.read_text(encoding="utf-8").strip().splitlines()[-1] for p in outputs} == {"Factura 2024", "Factura 2025"}
