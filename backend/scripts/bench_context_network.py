"""Coste de leer las propiedades de los originales al construir el contexto, en red frente a local (W0, doc_organize 1.5.0).

Desde doc_organize 1.5.0, ``ContextBuilder.build()`` abre cada original con ``read_document_properties`` para leer su
autor, descripción y palabras clave, de uno en uno. En local cuesta menos de 0,5 ms por documento; este script lo mide
sobre una carpeta de red (SMB/NFS) y sobre una copia local de los mismos ficheros.

**Solo lee del origen**: no escanea, no convierte y no escribe nada en la carpeta medida. La copia local va a una
carpeta temporal que se borra al terminar (salvo ``--keep-copy``).

Pasadas, cada una sobre una muestra aleatoria **distinta** (misma semilla, sin repetir ficheros) para que todas sean
primera lectura desde este equipo:

1. ``red-secuencial``: un fichero detrás de otro, como hace hoy la librería.
2. ``red-hilos-K``: la misma lectura con K hilos (``--workers``), para saber si leer en paralelo compensaría (G44).
   Ojo: PDFium no es thread-safe y aquí se llama en paralelo; sirve para medir el techo de la mejora, no como diseño.
3. ``red-repetida``: la muestra 1 otra vez tras ``--pause`` segundos (caché del cliente SMB caliente).
4. ``local``: la muestra 1 copiada a disco local (referencia, con la misma condición de primera lectura que la red).
5. ``local-repetida``: la copia local otra vez. En Windows la primera apertura de un fichero recién copiado cuesta unos
   7 ms (antivirus en tiempo real) y la segunda unos 0,4 ms; la razón red/local se calcula con ``local``.

No se puede garantizar una lectura «en frío»: el servidor de ficheros y Windows pueden tener ya en caché ficheros que
alguien abrió hace poco. Por eso se habla de «primera lectura desde este equipo».

    uv run --frozen python scripts/bench_context_network.py "\\\\SERVIDOR\\recurso\\carpeta"
    uv run --frozen python scripts/bench_context_network.py RUTA --sample 300 --workers 4,8 --report ../build/logs/w0.json

Sale con 2 si se supera el umbral de decisión del plan (p95 > ``--p95-ms`` o red > ``--ratio`` × local): entonces se
pide a la librería la lectura concurrente de propiedades (G44) antes de extenderla a los sin clasificar (G42).
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import random
import shutil
import statistics
import sys
import tempfile
import time
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

#: Extensiones de las que ``read_document_properties`` lee algo (PDF y Office OOXML); el resto no abre el fichero.
SUPPORTED = frozenset({".pdf", ".docx", ".docm", ".xlsx", ".xlsm", ".pptx", ".pptm"})


@dataclass
class Sample:
    """Un fichero medido: tiempos en milisegundos."""

    relative: str
    extension: str
    size_bytes: int
    stat_ms: float
    properties_ms: float
    found: bool  # si declaraba autor, descripción o palabras clave


@dataclass
class Pass:
    """Resultado de una pasada."""

    name: str
    workers: int
    files: int
    wall_s: float
    samples: list[Sample] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        props = [s.properties_ms for s in self.samples]
        stats = [s.stat_ms for s in self.samples]
        return {
            "name": self.name,
            "workers": self.workers,
            "files": self.files,
            "wall_s": round(self.wall_s, 2),
            "ms_per_doc_effective": round(self.wall_s * 1000 / self.files, 2) if self.files else None,
            "properties_ms": _percentiles(props),
            "stat_ms": _percentiles(stats),
            "by_extension": {
                ext: _percentiles([s.properties_ms for s in self.samples if s.extension == ext])
                for ext in sorted({s.extension for s in self.samples})
            },
            "with_properties": sum(s.found for s in self.samples),
        }


def _percentiles(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"p50": None, "p95": None, "max": None, "mean": None}
    ordered = sorted(values)
    p95 = ordered[min(len(ordered) - 1, round(0.95 * (len(ordered) - 1)))]
    return {
        "p50": round(statistics.median(ordered), 2),
        "p95": round(p95, 2),
        "max": round(ordered[-1], 2),
        "mean": round(statistics.fmean(ordered), 2),
    }


def _measure_one(path: Path, root: Path, read: Callable[[Path], Any]) -> Sample:
    started = time.perf_counter()
    size = path.stat().st_size
    stat_ms = (time.perf_counter() - started) * 1000
    started = time.perf_counter()
    props = read(path)
    properties_ms = (time.perf_counter() - started) * 1000
    return Sample(
        relative=path.relative_to(root).as_posix(),
        extension=path.suffix.lower(),
        size_bytes=size,
        stat_ms=stat_ms,
        properties_ms=properties_ms,
        found=bool(props.author or props.description or props.keywords),
    )


def _run_pass(name: str, files: list[Path], root: Path, workers: int, read: Callable[[Path], Any]) -> Pass:
    print(f"  {name}: {len(files)} ficheros, {workers} hilo(s)…", file=sys.stderr, flush=True)
    started = time.perf_counter()
    if workers == 1:
        samples = [_measure_one(path, root, read) for path in files]
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            samples = list(pool.map(lambda path: _measure_one(path, root, read), files))
    return Pass(name=name, workers=workers, files=len(files), wall_s=time.perf_counter() - started, samples=samples)


def _list_supported(root: Path) -> tuple[list[Path], float, int]:
    started = time.perf_counter()
    found: list[Path] = []
    total = 0
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            total += 1
            if os.path.splitext(name)[1].lower() in SUPPORTED:
                found.append(Path(dirpath) / name)
    found.sort()
    return found, time.perf_counter() - started, total


def _copy_local(files: list[Path], root: Path, target: Path) -> tuple[list[Path], float, int]:
    started = time.perf_counter()
    copied: list[Path] = []
    total_bytes = 0
    for path in files:
        destination = target / path.relative_to(root)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        total_bytes += destination.stat().st_size
        copied.append(destination)
    return copied, time.perf_counter() - started, total_bytes


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# W0 — Propiedades de los originales en red ({report['started_at'][:10]})",
        "",
        f"- Origen: `{report['source']}`",
        f"- Equipo: {report['host']['system']} {report['host']['release']}, Python {report['host']['python']}, "
        f"doc_organize {report['doc_organize_version']}",
        f"- Ficheros en el origen: {report['listing']['files_total']} "
        f"({report['listing']['supported']} PDF/Office); listado en {report['listing']['seconds']} s",
        f"- Muestra por pasada: {report['sample_size']} (semilla {report['seed']}); "
        f"extensiones de la muestra 1: {report['sample_extensions']}",
    ]
    if report.get("local_copy"):
        copy = report["local_copy"]
        lines.append(f"- Copia a local: {copy['mb']} MB en {copy['seconds']} s ({copy['mb_per_s']} MB/s)")
    lines += [
        "",
        "| Pasada | Hilos | Ficheros | Total (s) | ms/doc efectivo | p50 | p95 | máx | stat p50 | Con propiedades |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for p in report["passes"]:
        props = p["properties_ms"]
        lines.append(
            f"| {p['name']} | {p['workers']} | {p['files']} | {p['wall_s']} | {p['ms_per_doc_effective']} | "
            f"{props['p50']} | {props['p95']} | {props['max']} | {p['stat_ms']['p50']} | {p['with_properties']} |"
        )
    lines += ["", "## Por extensión (red-secuencial, ms)", "", "| Extensión | p50 | p95 | máx |", "|---|---|---|---|"]
    first = report["passes"][0]
    for ext, values in first["by_extension"].items():
        lines.append(f"| {ext} | {values['p50']} | {values['p95']} | {values['max']} |")
    estimate = report["estimate"]
    decision = report["decision"]
    lines += [
        "",
        "## Estimación y decisión",
        "",
        f"- Coste añadido al construir el contexto de toda la carpeta ({estimate['supported']} documentos), secuencial: "
        f"**{estimate['sequential_s']} s**"
        + (
            f"; con {estimate['best_workers']} hilos: {estimate['best_parallel_s']} s"
            if estimate.get("best_workers")
            else ""
        ),
        f"- Umbral: p95 > {decision['p95_threshold_ms']} ms o red > {decision['ratio_threshold']}× local. "
        f"p95 red = {decision['network_p95_ms']} ms; ratio p50 red/local = {decision['ratio']}",
        f"- **{'Supera el umbral: pedir G44 (lectura concurrente) antes de L5' if decision['exceeded'] else 'No supera el umbral: L5 puede seguir sin G44'}**",
        "",
        "Las pasadas «red-*» son primera lectura desde este equipo; el servidor de ficheros puede tener datos en caché.",
    ]
    return "\n".join(lines) + "\n"


def _local_passes(
    files: list[Path], root: Path, keep_copy: bool, read: Callable[[Path], Any]
) -> tuple[dict[str, Any], list[Pass]]:
    """Copia ``files`` a una carpeta temporal y la mide dos veces (primera lectura y repetida)."""
    target = Path(tempfile.mkdtemp(prefix="w0_local_"))
    try:
        print(f"  copiando la muestra a {target}…", file=sys.stderr, flush=True)
        copied, copy_s, copy_bytes = _copy_local(files, root, target)
        mb = copy_bytes / 1_000_000
        copy = {"mb": round(mb, 1), "seconds": round(copy_s, 2), "mb_per_s": round(mb / copy_s, 1) if copy_s else None}
        return copy, [
            _run_pass("local", copied, target, 1, read),
            _run_pass("local-repetida", copied, target, 1, read),
        ]
    finally:
        if keep_copy:
            print(f"  copia conservada en {target}", file=sys.stderr)
        else:
            shutil.rmtree(target, ignore_errors=True)


def _decision(summaries: list[dict[str, Any]], p95_threshold: float, ratio_threshold: float) -> dict[str, Any]:
    """Umbral del plan: p95 secuencial en red, o razón de medianas red/local (primera lectura en los dos)."""
    sequential = summaries[0]
    local = next((s for s in summaries if s["name"] == "local"), None)
    network_p50 = sequential["properties_ms"]["p50"] or 0.0
    local_p50 = local["properties_ms"]["p50"] if local else None
    ratio = round(network_p50 / local_p50, 1) if local_p50 else None
    network_p95 = sequential["properties_ms"]["p95"] or 0.0
    return {
        "p95_threshold_ms": p95_threshold,
        "ratio_threshold": ratio_threshold,
        "network_p95_ms": network_p95,
        "ratio": ratio,
        "exceeded": network_p95 > p95_threshold or (ratio is not None and ratio > ratio_threshold),
    }


def _estimate(summaries: list[dict[str, Any]], supported: int) -> dict[str, Any]:
    """Coste añadido para toda la carpeta, secuencial y con el mejor número de hilos probado."""
    estimate: dict[str, Any] = {
        "supported": supported,
        "sequential_s": round(summaries[0]["ms_per_doc_effective"] * supported / 1000, 1),
    }
    parallel = [s for s in summaries if s["name"].startswith("red-hilos-")]
    if parallel:
        best = min(parallel, key=lambda s: s["ms_per_doc_effective"])
        estimate["best_workers"] = best["workers"]
        estimate["best_parallel_s"] = round(best["ms_per_doc_effective"] * supported / 1000, 1)
    return estimate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("source", type=Path, help="Carpeta de red con los originales (solo se lee)")
    parser.add_argument("--sample", type=int, default=200, help="Ficheros por pasada (200)")
    parser.add_argument("--workers", default="4,8", help="Niveles de hilos a probar, separados por comas (4,8)")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--pause", type=float, default=15.0, help="Segundos antes de la pasada repetida (15)")
    parser.add_argument("--no-local", action="store_true", help="Sin copia local de referencia")
    parser.add_argument("--keep-copy", action="store_true", help="No borrar la copia local")
    parser.add_argument("--report", type=Path, help="JSON con el detalle (y .md al lado)")
    parser.add_argument("--p95-ms", type=float, default=20.0)
    parser.add_argument("--ratio", type=float, default=3.0)
    args = parser.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    import doc_organize

    # La librería importa pypdfium2 en el primer PDF; se importa aquí para no medir la importación.
    import pypdfium2  # type: ignore[import-untyped]  # noqa: F401
    from doc_organize import read_document_properties

    root: Path = args.source
    if not root.is_dir():
        parser.error(f"no es una carpeta accesible: {root}")
    levels = sorted({int(value) for value in args.workers.split(",") if value.strip() and int(value) > 1})

    started_at = datetime.now(UTC).isoformat()
    print(f"Listando {root}…", file=sys.stderr, flush=True)
    supported, listing_s, files_total = _list_supported(root)
    needed = args.sample * (1 + len(levels))
    if len(supported) < needed:
        print(f"Solo hay {len(supported)} ficheros PDF/Office; se reparten entre las pasadas.", file=sys.stderr)
    # Muestreo reproducible, no criptográfico.
    shuffled = random.Random(args.seed).sample(supported, len(supported))  # noqa: S311
    chunk = min(args.sample, len(shuffled) // (1 + len(levels)))
    if chunk == 0:
        parser.error("no hay ficheros PDF/Office suficientes")
    subsets = [shuffled[i * chunk : (i + 1) * chunk] for i in range(1 + len(levels))]

    passes = [_run_pass("red-secuencial", subsets[0], root, 1, read_document_properties)]
    for level, subset in zip(levels, subsets[1:], strict=True):
        passes.append(_run_pass(f"red-hilos-{level}", subset, root, level, read_document_properties))
    print(f"  pausa de {args.pause:g} s…", file=sys.stderr, flush=True)
    time.sleep(args.pause)
    passes.append(_run_pass("red-repetida", subsets[0], root, 1, read_document_properties))

    local_copy: dict[str, Any] | None = None
    if not args.no_local:
        local_copy, local_passes = _local_passes(subsets[0], root, args.keep_copy, read_document_properties)
        passes.extend(local_passes)

    summaries = [p.summary() for p in passes]
    decision = _decision(summaries, args.p95_ms, args.ratio)
    estimate = _estimate(summaries, len(supported))
    exceeded = bool(decision["exceeded"])

    report: dict[str, Any] = {
        "started_at": started_at,
        "source": str(root),
        "host": {"system": platform.system(), "release": platform.release(), "python": platform.python_version()},
        "doc_organize_version": doc_organize.__version__,
        "listing": {"files_total": files_total, "supported": len(supported), "seconds": round(listing_s, 2)},
        "sample_size": chunk,
        "seed": args.seed,
        "sample_extensions": dict(Counter(path.suffix.lower() for path in subsets[0]).most_common()),
        "local_copy": local_copy,
        "passes": summaries,
        "estimate": estimate,
        "decision": decision,
        "samples": {p.name: [asdict(s) for s in p.samples] for p in passes},
    }
    markdown = _markdown(report)
    print(markdown)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        args.report.with_suffix(".md").write_text(markdown, encoding="utf-8")
        print(f"Informe: {args.report} y {args.report.with_suffix('.md')}", file=sys.stderr)
    return 2 if exceeded else 0


if __name__ == "__main__":
    raise SystemExit(main())
