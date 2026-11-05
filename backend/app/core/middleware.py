"""Middleware HTTP en ASGI puro (no rompe el *streaming* de SSE ni de los ZIP): ``request_id``, cabeceras de
seguridad y línea de acceso JSON.
"""

from __future__ import annotations

import logging
import time
from typing import Final

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import problem
from app.core.metrics import HttpMetrics, route_template
from app.core.request_context import REQUEST_ID_HEADER, accept_or_generate, bind_request_id, reset_request_id

logger = logging.getLogger(__name__)
access_logger = logging.getLogger("app.access")

#: SPA: sin scripts inline ni de terceros. Mantine inyecta ``<style>`` y usa ``style=``: ``'unsafe-inline'`` en
#: estilos. El sitio de contexto (Fase 7) se servirá con su propia CSP en un iframe ``sandbox``.
SPA_CSP: Final = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
    "font-src 'self' data:; connect-src 'self'; frame-src 'self'; worker-src 'self' blob:; object-src 'none'; "
    "base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
)
API_CSP: Final = "default-src 'none'; frame-ancestors 'none'"
SECURITY_HEADERS: Final = (
    ("X-Content-Type-Options", "nosniff"),
    ("Referrer-Policy", "same-origin"),
    ("X-Frame-Options", "DENY"),
    ("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=(), usb=()"),
    ("Cross-Origin-Opener-Policy", "same-origin"),
    ("Cross-Origin-Resource-Policy", "same-origin"),
)
_QUIET: Final = frozenset({"/api/health"})
#: Fase 10 (ASVS V14.4.5): solo con cookies ``Secure`` (fuera de ``development``), que ya exigen HTTPS en el proxy.
HSTS: Final = "max-age=31536000; includeSubDomains"
#: Fase 10 (ASVS V8.2.1): ninguna respuesta de la API (usuarios, auditoría, rutas) se guarda en cachés.
API_CACHE_CONTROL: Final = "no-store"


def loggable_path(path: str) -> str:
    """``path`` sin el token del sitio de contexto (``/site/<token>/…`` → ``/site/***/…``): es una credencial."""
    if path.startswith("/site/"):
        _, _, rest = path[len("/site/") :].partition("/")
        return f"/site/***/{rest}"
    return path


class RequestMiddleware:
    """Asigna ``request_id`` (cabecera ``X-Request-ID``), añade cabeceras de seguridad y registra cada petición."""

    def __init__(self, app: ASGIApp, metrics: HttpMetrics | None = None, *, hsts: bool = False) -> None:
        self.app = app
        self.metrics = metrics
        self.hsts = hsts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = accept_or_generate(Headers(scope=scope).get(REQUEST_ID_HEADER))
        token = bind_request_id(request_id)
        path = str(scope.get("path", ""))
        csp = API_CSP if path.startswith("/api") else SPA_CSP
        start = time.perf_counter()
        status = 500
        started = False

        async def send_with_headers(message: Message) -> None:
            nonlocal status, started
            if message["type"] == "http.response.start":
                started = True
                status = int(message["status"])
                headers = MutableHeaders(scope=message)
                headers[REQUEST_ID_HEADER] = request_id
                headers.setdefault("Content-Security-Policy", csp)
                for name, value in SECURITY_HEADERS:
                    headers.setdefault(name, value)
                if self.hsts:
                    headers.setdefault("Strict-Transport-Security", HSTS)
                if path.startswith("/api"):
                    headers.setdefault("Cache-Control", API_CACHE_CONTROL)
            await send(message)

        try:
            await self.app(scope, receive, send_with_headers)
        except Exception as exc:
            # Starlette responde los errores no controlados en ServerErrorMiddleware, por fuera de este middleware:
            # se responden aquí para conservar X-Request-ID, las cabeceras de seguridad y el request_id del cuerpo.
            if started:
                raise
            logger.error("Error no controlado", extra={"path": loggable_path(path), "exc_type": type(exc).__name__})
            await problem(500, "Error interno")(scope, receive, send_with_headers)
        finally:
            elapsed = time.perf_counter() - start
            if self.metrics is not None:
                # La plantilla de la ruta (la pone el router de Starlette en el scope), nunca la ruta real.
                route = route_template(path, scope.get("route"))
                self.metrics.observe(str(scope.get("method")), route, status, elapsed)
            if path not in _QUIET:
                access_logger.info(
                    "Petición HTTP",
                    extra={
                        "method": scope.get("method"),
                        "path": loggable_path(path),
                        "status": status,
                        "duration_ms": round(elapsed * 1000, 1),
                    },
                )
            reset_request_id(token)


class BodyLimitMiddleware:
    """Rechaza cuerpos de petición mayores que ``max_bytes`` antes de leerlos (Fase 10, ASVS V13.1.3).

    La API solo recibe JSON y los navegadores siempre envían ``Content-Length``: con él se decide sin leer nada (413);
    una escritura sin él (``Transfer-Encoding: chunked``) se rechaza con 411. Lo más grande que acepta la API es un
    ``dedup_apply`` de 10 000 grupos.
    """

    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") not in {"POST", "PUT", "PATCH"}:
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        length = headers.get("content-length")
        if length is None and "chunked" in headers.get("transfer-encoding", "").lower():
            response = problem(
                411, "Falta Content-Length", "La petición debe indicar su tamaño.", code="length_required"
            )
        elif length is not None and (not length.isdigit() or int(length) > self.max_bytes):
            response = problem(
                413,
                "Petición demasiado grande",
                f"El cuerpo de la petición pasa de {self.max_bytes // (1024 * 1024)} MiB.",
                code="body_too_large",
            )
        else:
            await self.app(scope, receive, send)
            return
        await response(scope, receive, send)
