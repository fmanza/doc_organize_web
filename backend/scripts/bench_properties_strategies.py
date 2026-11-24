"""Estrategias para leer en paralelo las propiedades de los originales sin llamar a PDFium a la vez (G44, doc_organize 1.6.0).

Complementa ``bench_context_network.py`` (W0): aquella midió que leer las propiedades de uno en uno cuesta 55 ms de
mediana por documento en SMB y que con hilos baja a ~30 ms, pero llamando a PDFium desde varios hilos, que no es
seguro (pypdfium2: «Incompatibility with Threading»). Aquí se miden las alternativas seguras:

- ``secuencial``: uno detrás de otro, como doc_organize 1.5.0.
- ``hilos-sin-cerrojo-K``: techo de la mejora (inseguro; solo referencia).
- ``cerrojo-pdf-K``: Office en K hilos; cada PDF se abre por ruta bajo un cerrojo, así que su E/S de red también se
  serializa.
- ``bytes-pdf-K`` (opción A): el hilo lee los bytes del PDF (la E/S de red) y solo ``PdfDocument(bytes)`` va bajo el
  cerrojo. Por encima de ``--max-bytes`` se abre por ruta bajo el cerrojo.
- ``procesos-K`` (opción B): pool de K procesos, incluido su arranque.

**Solo lee del origen.** Cada pasada usa una muestra distinta (primera lectura desde este equipo) y se excluyen los
ficheros ya leídos por el informe de W0 (``--exclude-report``). La opción A comprueba con un contador que PDFium nunca
se llama dos veces a la vez.

    uv run --frozen python scripts/bench_properties_strategies.py "\\\\SERVIDOR\\recurso\\carpeta" \
        --exclude-report ../build/logs/w0.json --report ../build/logs/g44.json
"""

from __future__ import annotations

import argparse
import json
import platform
import random
import re
import sys
import threading
import time
from collections import Counter
from collections.abc import Callable
from concurrent.futures import Executor, ProcessPoolExecutor, ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bench_context_network import _list_supported, _percentiles

_PDFIUM_LOCK = threading.Lock()


# Copia de ``doc_organize.utils.text_clean`` (interno de la librería; no está en su API pública desde la 2.4.0): mismo
# saneado que ``read_document_properties`` para que la opción A sea comparable.
def _clean_text(value: object, max_length: int = 500) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.split())
    return text[:max_length] or None


def _clean_keywords(values: object, limit: int = 20) -> list[str]:
    if isinstance(values, str):
        candidates: list[object] = list(re.split(r"[,;]", values))
    elif isinstance(values, list):
        candidates = values
    else:
        return []
    keywords: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        keyword = _clean_text(candidate, 60)
        if keyword is None or keyword.casefold() in seen:
            continue
        seen.add(keyword.casefold())
        keywords.append(keyword)
    return keywords[:limit]


_active = 0
_max_active = 0


def _pdfium_enter() -> None:
    global _active, _max_active
    _active += 1
    _max_active = max(_max_active, _active)


def _pdfium_exit() -> None:
    global _active
    _active -= 1


def _read_plain(path: Path) -> Any:
    from doc_organize import read_document_properties

    return read_document_properties(path)


def _read_pdf_locked(path: Path) -> Any:
    from doc_organize import read_document_properties

    if path.suffix.lower() != ".pdf":
        return read_document_properties(path)
    with _PDFIUM_LOCK:
        _pdfium_enter()
        try:
            return read_document_properties(path)
        finally:
            _pdfium_exit()


def _make_read_pdf_bytes(max_bytes: int) -> Callable[[Path], Any]:
    import pypdfium2 as pdfium  # type: ignore[import-untyped]
    from doc_organize import DocumentProperties, read_document_properties

    def read(path: Path) -> Any:
        if path.suffix.lower() != ".pdf":
            return read_document_properties(path)
        try:
            if path.stat().st_size > max_bytes:
                return _read_pdf_locked(path)
            data = path.read_bytes()  # E/S de red, fuera del cerrojo
        except OSError:
            return DocumentProperties()
        with _PDFIUM_LOCK:
            _pdfium_enter()
            try:
                pdf = pdfium.PdfDocument(data)
                try:
                    info = pdf.get_metadata_dict(skip_empty=True)
                finally:
                    pdf.close()
            except pdfium.PdfiumError:
                return DocumentProperties()
            finally:
                _pdfium_exit()
        return DocumentProperties(
            author=_clean_text(info.get("Author")),
            description=_clean_text(info.get("Subject")),
            keywords=_clean_keywords(info.get("Keywords")),
        )

    return read


def _timed_plain(path: Path) -> tuple[float, bool]:
    """Para el pool de procesos: tiene que ser una función de módulo."""
    started = time.perf_counter()
    props = _read_plain(path)
    return (time.perf_counter() - started) * 1000, bool(props.author or props.description or props.keywords)


def _run(name: str, files: list[Path], workers: int, read: Callable[[Path], Any] | None) -> dict[str, Any]:
    print(f"  {name}: {len(files)} ficheros…", file=sys.stderr, flush=True)

    reader = read or _read_plain  # con read=None se usa el pool de procesos y _timed_plain

    def timed(path: Path) -> tuple[float, bool]:
        started = time.perf_counter()
        props = reader(path)
        return (time.perf_counter() - started) * 1000, bool(props.author or props.description or props.keywords)

    started = time.perf_counter()
    if workers == 1:
        results = [timed(path) for path in files]
    else:
        pool: Executor = ProcessPoolExecutor(workers) if read is None else ThreadPoolExecutor(workers)
        with pool:
            results = list(pool.map(_timed_plain if read is None else timed, files))
    wall = time.perf_counter() - started
    return {
        "name": name,
        "workers": workers,
        "files": len(files),
        "pdf": sum(path.suffix.lower() == ".pdf" for path in files),
        "wall_s": round(wall, 2),
        "ms_per_doc_effective": round(wall * 1000 / len(files), 2),
        "properties_ms": _percentiles([ms for ms, _ in results]),
        "with_properties": sum(found for _, found in results),
    }


def _excluded(report: Path | None) -> set[str]:
    if report is None:
        return set()
    data = json.loads(report.read_text(encoding="utf-8"))
    return {sample["relative"] for samples in data["samples"].values() for sample in samples}


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# G44 — Estrategias de lectura concurrente de propiedades ({report['started_at'][:10]})",
        "",
        f"- Origen: `{report['source']}`",
        f"- Equipo: {report['host']}, doc_organize {report['doc_organize_version']}",
        f"- Muestra por pasada: {report['sample_size']} (semilla {report['seed']}), sin los {report['excluded']} ficheros de W0",
        f"- Llamadas simultáneas máximas a PDFium en las estrategias con cerrojo: {report['pdfium_max_concurrent']}",
        "",
        "| Pasada | Hilos/procesos | Ficheros (PDF) | Total (s) | ms/doc efectivo | p50 | p95 | máx | Con propiedades |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for p in report["passes"]:
        ms = p["properties_ms"]
        lines.append(
            f"| {p['name']} | {p['workers']} | {p['files']} ({p['pdf']}) | {p['wall_s']} | {p['ms_per_doc_effective']} | "
            f"{ms['p50']} | {ms['p95']} | {ms['max']} | {p['with_properties']} |"
        )
    lines += ["", f"Estimación para {report['supported']} documentos (ms/doc efectivo × documentos):", ""]
    lines += [
        f"- {p['name']}: {round(p['ms_per_doc_effective'] * report['supported'] / 1000, 1)} s" for p in report["passes"]
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("source", type=Path, help="Carpeta de red con los originales (solo se lee)")
    parser.add_argument("--sample", type=int, default=200, help="Ficheros por pasada (200)")
    parser.add_argument("--workers", type=int, default=4, help="Hilos o procesos de las pasadas concurrentes (4)")
    parser.add_argument("--extra-workers", type=int, default=8, help="Segundo nivel para la opción A; 0 = no (8)")
    parser.add_argument("--max-bytes", type=int, default=16_000_000, help="Opción A: mayor que esto, por ruta (16 MB)")
    parser.add_argument("--seed", type=int, default=2)
    parser.add_argument("--exclude-report", type=Path, help="Informe JSON de W0 cuyos ficheros no se reutilizan")
    parser.add_argument("--report", type=Path, help="JSON con el resultado (y .md al lado)")
    args = parser.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    import doc_organize

    # Se importa aquí para no medir la importación en el primer PDF.
    import pypdfium2  # noqa: F401

    root: Path = args.source
    if not root.is_dir():
        parser.error(f"no es una carpeta accesible: {root}")
    k = args.workers
    plan: list[tuple[str, int, Callable[[Path], Any] | None]] = [
        ("secuencial", 1, _read_plain),
        (f"hilos-sin-cerrojo-{k}", k, _read_plain),
        (f"cerrojo-pdf-{k}", k, _read_pdf_locked),
        (f"bytes-pdf-{k}", k, _make_read_pdf_bytes(args.max_bytes)),
    ]
    if args.extra_workers > 1:
        plan.append((f"bytes-pdf-{args.extra_workers}", args.extra_workers, _make_read_pdf_bytes(args.max_bytes)))
    plan.append((f"procesos-{k}", k, None))

    started_at = datetime.now(UTC).isoformat()
    print(f"Listando {root}…", file=sys.stderr, flush=True)
    supported, _listing_s, _total = _list_supported(root)
    excluded = _excluded(args.exclude_report)
    candidates = [path for path in supported if path.relative_to(root).as_posix() not in excluded]
    shuffled = random.Random(args.seed).sample(candidates, len(candidates))  # noqa: S311  # muestreo reproducible
    chunk = min(args.sample, len(shuffled) // len(plan))
    if chunk == 0:
        parser.error("no hay ficheros PDF/Office suficientes")

    passes = [
        _run(name, shuffled[i * chunk : (i + 1) * chunk], workers, read) for i, (name, workers, read) in enumerate(plan)
    ]
    report: dict[str, Any] = {
        "started_at": started_at,
        "source": str(root),
        "host": f"{platform.system()} {platform.release()}, Python {platform.python_version()}",
        "doc_organize_version": doc_organize.__version__,
        "supported": len(supported),
        "excluded": len(supported) - len(candidates),
        "sample_size": chunk,
        "seed": args.seed,
        "sample_extensions": dict(Counter(path.suffix.lower() for path in shuffled[: chunk * len(plan)]).most_common()),
        "pdfium_max_concurrent": _max_active,
        "passes": passes,
    }
    markdown = _markdown(report)
    print(markdown)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        args.report.with_suffix(".md").write_text(markdown, encoding="utf-8")
        print(f"Informe: {args.report} y {args.report.with_suffix('.md')}", file=sys.stderr)
    return 1 if _max_active > 1 else 0


if __name__ == "__main__":
    raise SystemExit(main())
