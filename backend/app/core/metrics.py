"""Métricas HTTP del proceso para ``/metrics`` (Fase 10), en formato de texto de Prometheus escrito a mano.

Solo etiquetas acotadas: método, **plantilla** de la ruta (``/api/v1/projects/{project_id}``, nunca la ruta real, que
llevaría ids o nombres) y código de estado. Una petición que no casa con ninguna ruta cuenta como ``unmatched``.
"""

from __future__ import annotations

import threading
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Final

#: Límites (segundos) del histograma de duración.
BUCKETS: Final = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)


def escape(value: str) -> str:
    """Valor de etiqueta con ``\\``, ``"`` y saltos de línea escapados (formato de texto 0.0.4)."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def labels(**values: str) -> str:
    """``{k="v",…}`` en el orden dado; vacío sin etiquetas."""
    if not values:
        return ""
    return "{" + ",".join(f'{key}="{escape(value)}"' for key, value in values.items()) + "}"


def route_template(path: str, route: object) -> str:
    """Plantilla completa de la ruta que atendió ``path`` (``/api/v1/projects/{project_id}``) o ``unmatched``.

    El ``scope["route"]`` de FastAPI es la ruta del router incluido, sin el prefijo de quien lo incluye: el prefijo se
    recupera como el tramo inicial de ``path`` tras el que la expresión de la ruta casa con el resto.
    """
    template, regex = getattr(route, "path", None), getattr(route, "path_regex", None)
    if not isinstance(template, str) or regex is None:
        return "unmatched"
    for index, char in enumerate(path):
        if char == "/" and regex.match(path[index:]):
            return path[:index] + template
    return "unmatched"


@dataclass
class _Histogram:
    counts: list[int] = field(default_factory=lambda: [0] * len(BUCKETS))
    total: int = 0
    sum: float = 0.0


class HttpMetrics:
    """Contadores de peticiones y duraciones por (método, ruta plantilla, estado), seguros entre hilos."""

    def __init__(self) -> None:
        self._requests: dict[tuple[str, str, str], int] = {}
        self._durations: dict[tuple[str, str], _Histogram] = {}
        self._lock = threading.Lock()

    def observe(self, method: str, route: str, status: int, seconds: float) -> None:
        """Anota una petición terminada."""
        with self._lock:
            key = (method, route, str(status))
            self._requests[key] = self._requests.get(key, 0) + 1
            histogram = self._durations.setdefault((method, route), _Histogram())
            for index, bound in enumerate(BUCKETS):
                if seconds <= bound:
                    histogram.counts[index] += 1
            histogram.total += 1
            histogram.sum += seconds

    def render(self) -> Iterable[str]:
        """Líneas de las métricas HTTP."""
        with self._lock:
            requests = sorted(self._requests.items())
            durations = sorted((key, _Histogram(list(h.counts), h.total, h.sum)) for key, h in self._durations.items())
        yield "# HELP dow_http_requests_total Peticiones HTTP atendidas."
        yield "# TYPE dow_http_requests_total counter"
        for (method, route, status), count in requests:
            yield f"dow_http_requests_total{labels(method=method, route=route, status=status)} {count}"
        yield "# HELP dow_http_request_duration_seconds Duración de las peticiones HTTP."
        yield "# TYPE dow_http_request_duration_seconds histogram"
        for (method, route), histogram in durations:
            for bound, count in zip(BUCKETS, histogram.counts, strict=True):
                yield (
                    "dow_http_request_duration_seconds_bucket"
                    f"{labels(method=method, route=route, le=str(bound))} {count}"
                )
            yield (
                f"dow_http_request_duration_seconds_bucket{labels(method=method, route=route, le='+Inf')} "
                f"{histogram.total}"
            )
            yield f"dow_http_request_duration_seconds_sum{labels(method=method, route=route)} {histogram.sum:.6f}"
            yield f"dow_http_request_duration_seconds_count{labels(method=method, route=route)} {histogram.total}"
