"""LiteLLM Proxy falso para los E2E (solo ``docker-compose.e2e.yml``; nunca en producción), con el formato que espera
el cliente único de doc_organize 2.0 (``LlmClient``):

- ``POST /chat/completions`` con ``response_format`` ``json_schema`` **estricto** (``strict: true``; si no, 400): la
  tarea sale de ``metadata.tags`` (``task:<tarea>``). ``taxonomy_design`` devuelve un borrador fijo; el resto, un JSON
  generado del propio esquema (en la clasificación, el primer valor del ``enum`` de cada eje). Con ``json_object`` (la
  caída de 2.0) responde lo mismo.
- ``POST /embeddings``: vectores fijos deterministas.
- ``GET /key/info``: gasto fijo de la clave.

Solo acepta la clave ``FAKE_LITELLM_KEY`` (por defecto ``sk-e2e-fake``); con otra responde 401. Sin dependencias: corre
con el Python de la imagen de la aplicación. Solo datos sintéticos.
"""

from __future__ import annotations

import hashlib
import json
import os
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
    "profile": {"context": "Proyecto sintético de los E2E.", "tie_breakers": None, "glossary": None},
    "reasoning": "Borrador del LiteLLM falso de los E2E.",
}


def sample(schema: dict[str, Any]) -> Any:
    """Una instancia que cumple ``schema`` (el subconjunto de JSON Schema que usa doc_organize)."""
    kind = schema.get("type")
    if "enum" in schema:
        return schema["enum"][0]
    if isinstance(kind, list):
        return None if "null" in kind else sample({**schema, "type": kind[0]})
    if kind == "object":
        properties = schema.get("properties", {})
        return {name: sample(properties[name]) for name in schema.get("required", list(properties))}
    if kind == "array":
        return [sample(schema["items"])] if "items" in schema else []
    if kind == "string":
        return "Texto del LiteLLM falso de los E2E."
    if kind == "number":
        return 0.9
    if kind == "integer":
        return 1
    if kind == "boolean":
        return True
    return None


_schemas: dict[str, dict[str, Any]] = {}


def _answer(body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    tags = (body.get("metadata") or {}).get("tags") or []
    task = next((tag.removeprefix("task:") for tag in tags if tag.startswith("task:")), "")
    response_format = body.get("response_format") or {}
    if response_format.get("type") == "json_schema":
        spec = response_format.get("json_schema") or {}
        if spec.get("strict") is not True or "schema" not in spec:
            return 400, {"error": "se esperaba json_schema estricto"}
        _schemas[task] = spec["schema"]
    if task == "taxonomy_design":
        content: Any = DRAFT
    else:
        schema = _schemas.get(task)
        content = sample(schema) if schema else {}
    usage = {"prompt_tokens": 100, "completion_tokens": 20}
    return 200, {"choices": [{"message": {"content": json.dumps(content, ensure_ascii=False)}}], "usage": usage}


def _embeddings(body: dict[str, Any]) -> dict[str, Any]:
    inputs = body.get("input") or []
    inputs = inputs if isinstance(inputs, list) else [inputs]
    data = []
    for index, text in enumerate(inputs):
        digest = hashlib.sha256(str(text).encode("utf-8")).digest()
        data.append({"index": index, "embedding": [byte / 255 for byte in digest[:8]]})
    return {"data": data}


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
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length) or b"{}")
        path = self.path.rstrip("/")
        if path == "/chat/completions":
            self._send(*_answer(body))
        elif path == "/embeddings":
            self._send(200, _embeddings(body))
        else:
            self._send(404, {"error": "not found"})

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
