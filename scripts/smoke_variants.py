"""Comprueba una variante de la imagen **dentro de su contenedor** (Fase 10, WB-10.7). Solo documentos sintéticos.

Se ejecuta con el Python del contenedor, leyendo este fichero por la entrada estándar (la imagen no lleva ``scripts/``)::

    docker compose exec -T worker-gpu python - --gpu < scripts/smoke_variants.py
    docker compose exec -T worker python - --libreoffice --av < scripts/smoke_variants.py
    docker compose exec -T worker python - < scripts/smoke_variants.py          # solo la conversión con CPU

Siempre: la ficha de capacidades y una conversión real (HTML y un PDF escaneado con OCR) en ``/tmp``. Con ``--gpu``,
además, el OCR del PDF con la GPU (EasyOCR) y el tiempo frente a la CPU. ``--libreoffice`` y ``--av`` comprueban que
``soffice`` y ``ffmpeg``/Whisper están y responden. Sale con 1 si algo falla.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def _documents(folder: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont

    folder.mkdir(parents=True)
    (folder / "nota.html").write_text(
        "<html><body><h1>Nota sintetica</h1><p>Texto de prueba.</p></body></html>", encoding="utf-8"
    )
    image = Image.new("RGB", (1600, 400), "white")
    try:
        font = ImageFont.load_default(size=72)
    except TypeError:  # Pillow sin tamaño en la fuente por defecto
        font = ImageFont.load_default()
    ImageDraw.Draw(image).text((60, 150), "FACTURA SINTETICA 2026", fill="black", font=font)
    image.save(folder / "factura.pdf", "PDF", resolution=150)


def _scan(work: Path, *, use_gpu: bool) -> tuple[dict[str, object], float, str]:
    from app.core.config import get_settings
    from app.integrations.doc_organize import ScanRequest, run_scan

    name = "gpu" if use_gpu else "cpu"
    source = work / f"origen-{name}"
    _documents(source)
    (work / f"salidas-{name}").mkdir()
    request = ScanRequest(
        folders=[source],
        output_root=work / f"salidas-{name}",
        state_root=work / f"estado-{name}",
        models_dir=get_settings().models_dir,
        use_ocr=True,
        use_gpu=use_gpu,
    )
    start = time.perf_counter()
    outcome = run_scan(request, on_progress=lambda _: None, is_cancelled=lambda: False)
    elapsed = time.perf_counter() - start
    text = " ".join(p.read_text(encoding="utf-8") for p in (work / f"salidas-{name}").rglob("factura.md"))
    return outcome.summary, elapsed, text


def _version(command: list[str]) -> str | None:
    if shutil.which(command[0]) is None:
        return None
    result = subprocess.run(command, capture_output=True, text=True, timeout=120, check=False)
    return (result.stdout or result.stderr).strip().splitlines()[0] if result.returncode == 0 else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--gpu", action="store_true")
    parser.add_argument("--libreoffice", action="store_true")
    parser.add_argument("--av", action="store_true")
    args = parser.parse_args(argv)
    from app.integrations.doc_organize import run_probe

    capabilities = run_probe()
    print("Capacidades:", json.dumps(capabilities.__dict__, ensure_ascii=False))
    failures: list[str] = []
    with tempfile.TemporaryDirectory(dir="/tmp") as tmp:
        work = Path(tmp)
        summary, cpu_seconds, text = _scan(work, use_gpu=False)
        print(f"CPU: {summary.get('converted')} convertidos en {cpu_seconds:.1f} s")
        if summary.get("converted") != 2:
            failures.append(f"CPU: se esperaban 2 conversiones y hubo {summary.get('converted')}")
        if "FACTURA" not in text.upper():
            failures.append("CPU: el OCR no leyó el PDF escaneado")
        if args.gpu:
            if not capabilities.gpu_ready:
                failures.append("GPU: el worker no tiene GPU utilizable o le faltan los modelos de EasyOCR")
            else:
                summary, gpu_seconds, text = _scan(work, use_gpu=True)
                print(f"GPU: {summary.get('converted')} convertidos en {gpu_seconds:.1f} s")
                if summary.get("converted") != 2 or "FACTURA" not in text.upper():
                    failures.append("GPU: la conversión con EasyOCR no leyó el PDF escaneado")
    if args.libreoffice:
        version = _version(["soffice", "--headless", "--version"])
        print("LibreOffice:", version)
        if not capabilities.libreoffice_installed or version is None:
            failures.append("LibreOffice: soffice no está o no responde")
    if args.av:
        version = _version(["ffmpeg", "-version"])
        print("ffmpeg:", version, "· Whisper:", capabilities.asr_installed)
        if not capabilities.av_ready or version is None:
            failures.append("AV: falta ffmpeg o Whisper")
    for failure in failures:
        print("ERROR:", failure, file=sys.stderr)
    print("Variante correcta." if not failures else f"{len(failures)} comprobaciones fallidas.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
