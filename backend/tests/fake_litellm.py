"""LiteLLM Proxy falso para los tests de la IA de doc_organize 2.0 (W2): sustituye el transporte HTTP de la capa
anticorrupción (``app.integrations.doc_organize.ai._transport``) por un ``httpx.MockTransport``.

Imita lo que el cliente único (``LlmClient``) espera del proxy:

- ``POST /chat/completions`` con ``response_format`` ``json_schema`` **estricto**: comprueba que el esquema llega con
  ``strict: true`` y responde un JSON que lo cumple (generado del propio esquema, con sus ``enum``, o el que dé el
  test). Con ``json_schema=False`` responde 400 a ``json_schema``, como un modelo que no lo admite, y el cliente cae
  una vez a ``json_object``. Toda respuesta se valida contra el esquema recibido antes de enviarla.
- ``POST /chat/completions`` con ``tools`` (agentes): responde las ``tool_calls`` que dé el test o un mensaje final.
- ``POST /embeddings``: vectores deterministas a partir del texto.
- ``GET /key/info``: la información de la clave (modelos permitidos).
- Claves: solo acepta las de ``keys`` (401 con cualquier otra).

Guarda cada petición (ruta, tarea, clave usada y cuerpo) en ``requests`` para comprobar qué salió. Solo datos sintéticos.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest

from app.integrations.doc_organize import ai as library_ai

Answer = Callable[[dict[str, Any]], "dict[str, Any] | httpx.Response"]


@dataclass
class SentRequest:
    """Una petición recibida por el proxy falso."""

    path: str
    task: str | None
    key: str
    body: dict[str, Any]

    @property
    def response_format(self) -> str | None:
        return (self.body.get("response_format") or {}).get("type")

    @property
    def schema(self) -> dict[str, Any] | None:
        return (self.body.get("response_format") or {}).get("json_schema", {}).get("schema")


class SchemaMismatchError(AssertionError):
    """La respuesta preparada por el test no cumple el esquema que envió doc_organize."""


def sample(schema: dict[str, Any]) -> Any:
    """Una instancia mínima que cumple ``schema`` (el subconjunto de JSON Schema que usa doc_organize)."""
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
        return "texto"
    if kind == "number":
        return 0.8
    if kind == "integer":
        return 1
    if kind == "boolean":
        return True
    return None


def validate(value: Any, schema: dict[str, Any], path: str = "$") -> None:
    """Comprueba ``value`` contra ``schema`` como lo haría un proveedor con ``strict: true``.

    Raises:
        SchemaMismatchError: No lo cumple.
    """
    kinds = schema.get("type")
    kinds = kinds if isinstance(kinds, list) else [kinds] if kinds else []
    checks = {
        "object": lambda v: isinstance(v, dict),
        "array": lambda v: isinstance(v, list),
        "string": lambda v: isinstance(v, str),
        "number": lambda v: isinstance(v, int | float) and not isinstance(v, bool),
        "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
        "boolean": lambda v: isinstance(v, bool),
        "null": lambda v: v is None,
    }
    if kinds and not any(checks[kind](value) for kind in kinds):
        raise SchemaMismatchError(f"{path}: {value!r} no es {kinds}")
    if "enum" in schema and value not in schema["enum"]:
        raise SchemaMismatchError(f"{path}: {value!r} no está en {schema['enum']}")
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        missing = [name for name in schema.get("required", []) if name not in value]
        if missing:
            raise SchemaMismatchError(f"{path}: faltan {missing}")
        extra = [name for name in value if name not in properties]
        if extra and schema.get("additionalProperties") is False:
            raise SchemaMismatchError(f"{path}: sobran {extra}")
        for name, item in value.items():
            if name in properties:
                validate(item, properties[name], f"{path}.{name}")
    if isinstance(value, list) and "items" in schema:
        for index, item in enumerate(value):
            validate(item, schema["items"], f"{path}[{index}]")


def chat_response(content: dict[str, Any] | str, *, usage: tuple[int, int] = (120, 30)) -> httpx.Response:
    """Respuesta de ``/chat/completions`` con ``content`` (JSON) como mensaje del asistente."""
    text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"role": "assistant", "content": text}}],
            "usage": {"prompt_tokens": usage[0], "completion_tokens": usage[1]},
        },
    )


def embedding(text: str, dimensions: int = 8) -> list[float]:
    """Vector determinista de ``text`` (mismo texto, mismo vector)."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return [round(byte / 255, 4) for byte in digest[:dimensions]]


@dataclass
class FakeLiteLLM:
    """LiteLLM Proxy falso.

    Attributes:
        keys: Claves aceptadas (``Authorization: Bearer``).
        json_schema: Si los modelos admiten ``json_schema`` estricto (si no, 400 y el cliente cae a ``json_object``).
        answers: Tarea → función que recibe el cuerpo y devuelve el JSON de la respuesta (se valida contra el esquema)
            o una ``httpx.Response`` tal cual (errores, timeouts simulados...). Sin entrada, la respuesta se genera
            del esquema.
        tool_calls: Por cada llamada con ``tools``, las ``tool_calls`` que pide el «modelo» (lista vacía = respuesta
            final con ``final_text``).
        key_models: Modelos que ``/key/info`` dice que permite la clave (vacío = todos).
    """

    keys: set[str]
    json_schema: bool = True
    answers: dict[str, Answer] = field(default_factory=dict)
    tool_calls: list[list[dict[str, Any]]] = field(default_factory=list)
    final_text: str = "Hecho."
    key_models: list[str] = field(default_factory=list)
    requests: list[SentRequest] = field(default_factory=list)
    #: Último esquema pedido por tarea: con ``json_object`` el «modelo» sigue las instrucciones del prompt, que piden ese
    #: mismo JSON (lo que hace un modelo real tras la caída de ``json_schema``).
    _schemas: dict[str, dict[str, Any]] = field(default_factory=dict)

    def install(self, monkeypatch: pytest.MonkeyPatch) -> FakeLiteLLM:
        """Hace que los clientes de la capa anticorrupción hablen con este proxy."""
        monkeypatch.setattr(library_ai, "_transport", lambda _: httpx.MockTransport(self.handle))
        return self

    # --- vistas de lo recibido ------------------------------------------------------------------------------------

    def sent(self, task: str | None = None, path: str = "/chat/completions") -> list[SentRequest]:
        """Peticiones a ``path`` (de ``task``, si se da)."""
        return [r for r in self.requests if r.path.endswith(path) and (task is None or r.task == task)]

    def text_sent(self) -> str:
        """Todo lo que salió hacia el proxy, como texto (para buscar lo que no debe salir)."""
        return json.dumps([r.body for r in self.requests], ensure_ascii=False)

    # --- transporte -----------------------------------------------------------------------------------------------

    def handle(self, request: httpx.Request) -> httpx.Response:
        key = request.headers.get("authorization", "").removeprefix("Bearer ")
        body = json.loads(request.content) if request.content else {}
        tags = (body.get("metadata") or {}).get("tags") or []
        task = next((tag.removeprefix("task:") for tag in tags if tag.startswith("task:")), None)
        self.requests.append(SentRequest(path=request.url.path, task=task, key=key, body=body))
        if key not in self.keys:
            return httpx.Response(401, json={"error": "invalid key"})
        path = request.url.path
        if path.endswith("/key/info"):
            return httpx.Response(200, json={"key": "hash", "info": {"models": self.key_models, "spend": 0.0}})
        if path.endswith("/embeddings"):
            inputs = body["input"] if isinstance(body["input"], list) else [body["input"]]
            data = [{"index": i, "embedding": embedding(text)} for i, text in enumerate(inputs)]
            return httpx.Response(200, json={"data": data, "usage": {"prompt_tokens": len(inputs)}})
        if path.endswith("/chat/completions"):
            return self._chat(task, body)
        return httpx.Response(404)

    def _chat(self, task: str | None, body: dict[str, Any]) -> httpx.Response:
        if "tools" in body:
            calls = self.tool_calls.pop(0) if self.tool_calls else []
            message: dict[str, Any] = {"role": "assistant", "content": None if calls else self.final_text}
            if calls:
                message["tool_calls"] = calls
            return httpx.Response(200, json={"choices": [{"message": message}], "usage": {"prompt_tokens": 50}})
        response_format = body.get("response_format") or {}
        schema: dict[str, Any] | None = None
        if response_format.get("type") == "json_schema":
            spec = response_format["json_schema"]
            assert spec.get("strict") is True, "doc_organize pide json_schema estricto"
            self._schemas[task or ""] = spec["schema"]
            if not self.json_schema:
                return httpx.Response(400, json={"error": "response_format json_schema not supported"})
            schema = spec["schema"]
        answer = self.answers.get(task or "")
        expected = schema or self._schemas.get(task or "")
        content = answer(body) if answer is not None else (sample(expected) if expected else {})
        if isinstance(content, httpx.Response):
            return content
        if schema is not None:
            validate(content, schema)
        return chat_response(content)


def classify_answer(choices: dict[str, list[str]], *, confidence: float = 0.9, evidence: str | None = None) -> Answer:
    """Respuesta de ``classify`` que elige, por eje, los slugs de ``choices`` que el esquema permite (los demás ejes
    pedidos, sin valor). Así un test fija «la IA dice ``informes``» sin conocer qué ejes faltaban."""

    def _answer(body: dict[str, Any]) -> dict[str, Any]:
        schema = (body.get("response_format") or {}).get("json_schema", {}).get("schema")
        axes = [name for name in (schema or {}).get("properties", {}) if name != "reasoning"] if schema else []
        if not axes:  # json_object: sin esquema, se responde a los ejes de ``choices``
            axes = list(choices)
        result: dict[str, Any] = {"reasoning": "Respuesta sintética."}
        for axis in axes:
            allowed = None
            if schema:
                item = schema["properties"][axis]["properties"]["values"]["items"]
                allowed = item["properties"]["value"]["enum"]
            slugs = [slug for slug in choices.get(axis, []) if allowed is None or slug in allowed]
            result[axis] = {
                "values": [{"value": slug, "confidence": confidence, "evidence": evidence} for slug in slugs]
            }
        return result

    return _answer


def tool_call(name: str, arguments: dict[str, Any], index: int = 0) -> dict[str, Any]:
    """Una llamada a una herramienta, como la pide un modelo en ``tool_calls`` (para los guiones de los agentes)."""
    return {
        "id": f"call_{name}_{index}",
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments, ensure_ascii=False)},
    }
