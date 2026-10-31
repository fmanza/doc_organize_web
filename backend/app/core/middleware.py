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


class RequestMiddleware:
    """Asigna ``request_id`` (cabecera ``X-Request-ID``), añade cabeceras de seguridad y registra cada petición."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

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
            await send(message)

        try:
            await self.app(scope, receive, send_with_headers)
        except Exception as exc:
            # Starlette responde los errores no controlados en ServerErrorMiddleware, por fuera de este middleware:
            # se responden aquí para conservar X-Request-ID, las cabeceras de seguridad y el request_id del cuerpo.
            if started:
                raise
            logger.error("Error no controlado", extra={"path": path, "exc_type": type(exc).__name__})
            await problem(500, "Error interno")(scope, receive, send_with_headers)
        finally:
            if path not in _QUIET:
                access_logger.info(
                    "Petición HTTP",
                    extra={
                        "method": scope.get("method"),
                        "path": path,
                        "status": status,
                        "duration_ms": round((time.perf_counter() - start) * 1000, 1),
                    },
                )
            reset_request_id(token)
