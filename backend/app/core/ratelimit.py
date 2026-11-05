"""Límite de peticiones por IP (Fase 10, ASVS V2.2.1 y V11.1.4) en ASGI puro, en memoria del proceso.

Dos cubos con ventana deslizante de 60 s: el inicio de sesión (``DOW_RATE_LIMIT_LOGIN``) y las escrituras de
``/api/v1`` (``DOW_RATE_LIMIT_WRITE``). Se suma al bloqueo por cuenta (``login_max_attempts``), que no frena a quien
prueba muchas cuentas desde la misma IP.

En memoria basta mientras la API sea un único proceso uvicorn (el Dockerfile no usa ``--workers``). La IP es la del
par TCP o, detrás de un proxy de confianza (``FORWARDED_ALLOW_IPS``), la que uvicorn toma de ``X-Forwarded-For``.
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from collections.abc import Callable
from typing import Final

from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.errors import problem

WINDOW_SECONDS: Final = 60.0
LOGIN_PATH: Final = "/api/v1/auth/login"
WRITE_METHODS: Final = frozenset({"POST", "PUT", "PATCH", "DELETE"})
#: Claves vigiladas como mucho (una por IP y cubo): acota la memoria ante un barrido de IPs.
MAX_KEYS: Final = 100_000


class SlidingWindow:
    """Cuántas peticiones lleva cada clave en los últimos ``window`` segundos.

    Args:
        limit: Peticiones permitidas por ventana.
        window: Duración de la ventana en segundos.
        clock: Reloj monótono (sustituible en los tests).
    """

    def __init__(self, limit: int, window: float = WINDOW_SECONDS, clock: Callable[[], float] = time.monotonic) -> None:
        self.limit = limit
        self.window = window
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str) -> int:
        """Anota una petición de ``key``: 0 si cabe, o los segundos que faltan para que quepa otra."""
        now = self._clock()
        with self._lock:
            hits = self._hits.get(key)
            if hits is None:
                if len(self._hits) >= MAX_KEYS:
                    self._prune(now)
                hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= now - self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return max(1, math.ceil(hits[0] + self.window - now))
            hits.append(now)
            return 0

    def _prune(self, now: float) -> None:
        for key in [k for k, hits in self._hits.items() if not hits or hits[-1] <= now - self.window]:
            del self._hits[key]
        if len(self._hits) >= MAX_KEYS:  # todas activas: se olvida la más antigua antes que crecer sin límite
            del self._hits[next(iter(self._hits))]


class RateLimitMiddleware:
    """Responde 429 (*problem details*, ``code=rate_limited`` y ``Retry-After``) al pasar del límite.

    Args:
        app: Aplicación ASGI envuelta.
        login: Inicios de sesión por minuto e IP.
        write: Escrituras de ``/api/v1`` por minuto e IP (el inicio de sesión cuenta solo en su cubo).
    """

    def __init__(self, app: ASGIApp, *, login: int, write: int) -> None:
        self.app = app
        self.login = SlidingWindow(login)
        self.write = SlidingWindow(write)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") not in WRITE_METHODS:
            await self.app(scope, receive, send)
            return
        path = str(scope.get("path", ""))
        bucket = self.login if path == LOGIN_PATH else self.write if path.startswith("/api/v1/") else None
        client = scope.get("client")
        ip = str(client[0]) if client else "-"
        wait = bucket.hit(ip) if bucket is not None else 0
        if not wait:
            await self.app(scope, receive, send)
            return
        response = problem(
            429,
            "Demasiadas peticiones",
            f"Has hecho demasiadas peticiones seguidas; vuelve a intentarlo en {wait} s.",
            code="rate_limited",
        )
        response.headers["Retry-After"] = str(wait)
        await response(scope, receive, send)
