"""Diagnóstico del entorno con ``check_environment`` de doc_organize 2.0 (W4, F2).

``check_environment`` importa docling, torch (GPU) y construye un sitio de prueba con Zensical: tarda y ocupa memoria,
y la API no carga doc_organize al arrancar (G15). Por eso se ejecuta en un **subproceso**
(``python -m app.integrations.doc_organize.diagnostics``), como el sondeo de capacidades. Los modelos de IA a probar
(con sus claves) le llegan por la entrada estándar, nunca en la línea de órdenes, y el resultado sale en JSON por la
salida estándar.

Firma verificada en el tag ``v2.0.0rc2``::

    check_environment(*, check_ai=False, ai_endpoints=None, artifacts_path=None, build_site=True, transport=None)
        -> EnvironmentReport(checks=[EnvironmentCheck(name, status, detail, remedy)], checked_at)
    AiEndpoint(name, base_url, virtual_key, model, kind)   # la clave nunca aparece en el informe; kind (rc2)

doc_organize no pone claves ni rutas en el informe; aun así, el resultado se limpia aquí de las URL y claves que se le
dieron y de las rutas del contenedor que se pasen en ``redact``.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Final

logger = logging.getLogger(__name__)

#: Directorio que contiene el paquete ``app`` (``backend/`` en desarrollo, ``/app`` en la imagen).
_APP_PARENT: Final = Path(__file__).resolve().parents[3]
DIAGNOSTICS_TIMEOUT_SECONDS: Final = 300


@dataclass(frozen=True)
class AiEndpointSpec:
    """Un modelo de IA a comprobar: para qué se usa (``name``), proxy, clave y alias. La clave no sale en ``repr``."""

    name: str
    base_url: str
    virtual_key: str = field(repr=False)
    model: str
    #: ``chat`` (respuesta JSON) o ``embedding`` (un vector de ``/embeddings``, doc_organize 2.0.0rc2).
    kind: str = "chat"


@dataclass(frozen=True)
class DiagnosticCheck:
    name: str
    status: str
    detail: str
    remedy: str | None = None


@dataclass(frozen=True)
class DiagnosticsReport:
    checks: list[DiagnosticCheck]
    checked_at: str

    @property
    def ok(self) -> bool:
        """Sin errores (los avisos no cuentan, como ``EnvironmentReport.ok``)."""
        return all(check.status != "error" for check in self.checks)


def _clean(text: str | None, secrets: list[str]) -> str | None:
    if text is None:
        return None
    for secret in sorted((s for s in secrets if s), key=len, reverse=True):
        text = text.replace(secret, "«oculto»")
    return text


def run_diagnostics(
    *,
    check_ai: bool,
    endpoints: list[AiEndpointSpec],
    artifacts_path: Path | None,
    redact: list[str],
    timeout: float = DIAGNOSTICS_TIMEOUT_SECONDS,
) -> DiagnosticsReport:
    """Ejecuta ``check_environment`` en un subproceso y devuelve su informe, limpio de URL, claves y rutas.

    Raises:
        RuntimeError: El subproceso falló, se agotó el tiempo o su salida no es válida (sin detalles).
    """
    payload = {
        "check_ai": check_ai,
        "endpoints": [asdict(endpoint) for endpoint in endpoints],
        "artifacts_path": str(artifacts_path) if artifacts_path else None,
    }
    try:
        completed = subprocess.run(  # noqa: S603 - comando fijo con el intérprete actual
            [sys.executable, "-m", "app.integrations.doc_organize.diagnostics"],
            cwd=_APP_PARENT,
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("El diagnóstico no terminó a tiempo") from exc
    if completed.returncode != 0:
        raise RuntimeError(f"El diagnóstico terminó con código {completed.returncode}")
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    try:
        raw = json.loads(lines[-1])
        secrets = [*redact, *(e.base_url for e in endpoints), *(e.virtual_key for e in endpoints)]
        checks = [
            DiagnosticCheck(
                name=str(item["name"]),
                status=str(item["status"]),
                detail=_clean(str(item["detail"]), secrets) or "",
                remedy=_clean(item.get("remedy"), secrets),
            )
            for item in raw["checks"]
        ]
        return DiagnosticsReport(checks=checks, checked_at=str(raw["checked_at"]))
    except (IndexError, KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("Salida del diagnóstico no válida") from exc


def _main() -> dict[str, Any]:  # pragma: no cover - punto de entrada del subproceso (lo ejercitan los tests)
    import asyncio

    from doc_organize import AiEndpoint, check_environment

    payload = json.loads(sys.stdin.read() or "{}")
    endpoints = [AiEndpoint(**item) for item in payload.get("endpoints", [])]
    report = asyncio.run(
        check_environment(
            check_ai=bool(payload.get("check_ai")),
            ai_endpoints=endpoints,
            artifacts_path=payload.get("artifacts_path"),
            build_site=True,
        )
    )
    return {
        "checked_at": report.checked_at,
        "checks": [check.model_dump() for check in report.checks],
    }


if __name__ == "__main__":  # pragma: no cover - punto de entrada del subproceso
    logging.disable(logging.CRITICAL)
    print(json.dumps(_main(), ensure_ascii=False))
