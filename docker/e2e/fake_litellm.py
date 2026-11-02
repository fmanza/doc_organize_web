"""LiteLLM Proxy falso para los E2E de la Fase 8 (solo ``docker-compose.e2e.yml``; nunca en producción).

Responde lo mínimo que esperan los clientes de ``doc_organize.ai``:

- ``POST /chat/completions``: si el prompt pide un borrador de manifiesto, un catálogo fijo; si no, el primer dominio
  (y tipo de material) candidato del prompt.
- ``GET /key/info``: gasto fijo de la clave.

Solo acepta la clave ``FAKE_LITELLM_KEY`` (por defecto ``sk-e2e-fake``); con otra responde 401. Sin dependencias: corre
con el Python de la imagen de la aplicación.
"""

from __future__ import annotations

import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

KEY = os.environ.get("FAKE_LITELLM_KEY", "sk-e2e-fake")
PORT = int(os.environ.get("FAKE_LITELLM_PORT", "4000"))
DRAFT = {
    "domains": [
        {"slug": "facturas", "name": "Facturas", "description": "Facturas sintéticas", "keywords": ["factura"]},
        {"slug": "notas", "name": "Notas", "description": "Notas sintéticas", "keywords": ["nota"]},
    ],
    "material_types": [{"slug": "documento", "name": "Documento", "description": "Documento", "keywords": []}],
    "reasoning": "Borrador del LiteLLM falso de los E2E.",
}


def _first(label: str, prompt: str) -> str | None:
    match = re.search(rf"{label}:\s*([^\n]+)", prompt)
    if not match:
        return None
    first = match.group(1).split(",")[0].strip()
    return first or None


def _answer(body: dict[str, Any]) -> dict[str, Any]:
    prompt = "\n".join(str(m.get("content", "")) for m in body.get("messages", []))
    if "Propón el borrador" in prompt:
        content: dict[str, Any] = DRAFT
    else:
        content = {
            "domain": _first("Dominios candidatos", prompt),
            "confidence": 0.9,
            "domain_confidence": 0.9,
            "material_type": _first("Tipos de material candidatos", prompt),
            "material_type_confidence": 0.9,
            "reasoning": "Clasificado por el LiteLLM falso de los E2E.",
        }
    return {"choices": [{"message": {"content": json.dumps(content, ensure_ascii=False)}}]}


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _authorized(self) -> bool:
        if self.headers.get("Authorization") == f"Bearer {KEY}":
            return True
        self._send(401, {"error": "invalid key"})
        return False

    def do_POST(self) -> None:  # noqa: N802 - nombre de BaseHTTPRequestHandler
        if not self._authorized():
            return
        if self.path.rstrip("/") != "/chat/completions":
            self._send(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        self._send(200, _answer(json.loads(self.rfile.read(length) or b"{}")))

    def do_GET(self) -> None:  # noqa: N802 - nombre de BaseHTTPRequestHandler
        if self.path.startswith("/health"):
            self._send(200, {"status": "ok"})
            return
        if not self._authorized():
            return
        if self.path.startswith("/key/info"):
            self._send(200, {"info": {"spend": 0.42, "key_alias": "e2e"}})
            return
        self._send(404, {"error": "not found"})

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - firma de la clase base
        """Sin trazas de cada petición (no llevan nada útil y llenan el log de compose)."""


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()  # noqa: S104 - solo en la red de compose
