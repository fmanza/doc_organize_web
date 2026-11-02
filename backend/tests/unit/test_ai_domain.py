"""IA (Fase 8) sin red: cifrado MultiFernet, ``hint``, validación de ``base_url`` y clientes vigilados (G33, G34) con
los clientes reales de doc_organize sobre ``httpx.MockTransport``."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr

from app.core import crypto
from app.core.config import Settings
from app.domain.ai.errors import InvalidAiSettingError
from app.domain.ai.settings import hint, validate_base_url
from app.integrations.doc_organize import ai as library_ai
from app.integrations.doc_organize.ai import AiConnection, AiTally

KEY = "sk-unit-test-0000-abcd"


def _settings(*keys: str) -> Settings:
    return Settings(environment="test", fernet_keys=SecretStr(",".join(keys)) if keys else None)


def test_encrypt_roundtrip_and_rotation() -> None:
    old, new = Fernet.generate_key().decode(), Fernet.generate_key().decode()
    token = crypto.encrypt(_settings(old), KEY)
    assert KEY not in token
    assert crypto.decrypt(_settings(new, old), token) == KEY
    rotated = crypto.rotate(_settings(new, old), token)
    assert crypto.decrypt(_settings(new), rotated) == KEY
    with pytest.raises(crypto.UndecryptableError):
        crypto.decrypt(_settings(new), token)


@pytest.mark.parametrize("keys", [(), ("no-es-una-clave",), (" , ",)])
def test_encryption_not_configured(keys: tuple[str, ...]) -> None:
    settings = _settings(*keys)
    assert not crypto.is_configured(settings)
    with pytest.raises(crypto.EncryptionNotConfiguredError):
        crypto.encrypt(settings, KEY)


def test_hint_never_reveals_short_secrets() -> None:
    assert hint(KEY) == "…abcd"
    assert hint("abcd") == "***"
    assert hint("a") == "***"


@pytest.mark.parametrize(
    "url",
    ["https://litellm.example.internal", "http://litellm.example.internal:4000/v1/"],
)
def test_base_url_accepted(url: str) -> None:
    assert validate_base_url(url) == url.rstrip("/")


@pytest.mark.parametrize(
    "url",
    [
        "ftp://litellm.example.internal",
        "litellm.example.internal",
        "https://user:pass@litellm.example.internal",
        "https://litellm.example.internal/?key=1",
        "https://litellm.example.internal/#x",
        "https://litellm .example.internal",
        "https://litellm.example.internal:99999",
        "https://",
    ],
)
def test_base_url_rejected(url: str) -> None:
    with pytest.raises(InvalidAiSettingError):
        validate_base_url(url)


def _reply(content: dict[str, Any]) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(content)}}]})


def _classify(
    monkeypatch: pytest.MonkeyPatch, handler: Callable[[httpx.Request], httpx.Response], calls: int, budget: int = 100
) -> tuple[AiTally, list[Any], list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def _handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    monkeypatch.setattr(library_ai, "_transport", lambda _: httpx.MockTransport(_handle))
    connection = AiConnection(
        family="litellm_classification",
        values={"base_url": "https://litellm.example.internal", "virtual_key": KEY},
        budget=budget,
    )
    tally = AiTally()

    async def _run() -> list[Any]:
        outcomes: list[Any] = []
        async with library_ai.classification_client(connection, tally) as client:
            for _ in range(calls):
                try:
                    outcomes.append(await client.classify(chunks_text="texto", title="t", candidate_domains=["a", "b"]))
                except Exception as exc:  # noqa: BLE001 - se comprueba el tipo y el mensaje
                    outcomes.append(exc)
        return outcomes

    return tally, asyncio.run(_run()), seen


def test_guarded_client_counts_and_respects_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    tally, outcomes, seen = _classify(monkeypatch, lambda _: _reply({"domain": "a", "confidence": 0.9}), 5, budget=3)

    assert len(seen) == 3 and tally.calls == 3 and tally.classified == 3
    assert tally.stopped == "budget"
    assert [o.domain for o in outcomes] == ["a", "a", "a", None, None]
    assert seen[0].headers["authorization"] == f"Bearer {KEY}"


def test_guarded_client_stops_after_auth_error(monkeypatch: pytest.MonkeyPatch) -> None:
    tally, outcomes, seen = _classify(monkeypatch, lambda _: httpx.Response(401), 4)

    assert len(seen) == 1 and tally.stopped == "auth" and tally.failed == 1
    assert isinstance(outcomes[0], Exception)
    assert "example.internal" not in str(outcomes[0]) and KEY not in str(outcomes[0])
    assert all(o.domain is None for o in outcomes[1:])


def test_guarded_client_stops_after_consecutive_connection_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def _down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("caído", request=request)

    tally, _, seen = _classify(monkeypatch, _down, 6)

    assert len(seen) == library_ai.MAX_CONNECTION_FAILURES and tally.stopped == "connection"


def test_guarded_client_resets_connection_streak_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    answers = iter([httpx.ConnectError, None, httpx.ConnectError, None, httpx.ConnectError, None])

    def _flaky(request: httpx.Request) -> httpx.Response:
        error = next(answers)
        if error is not None:
            raise error("intermitente", request=request)
        return _reply({"domain": "b"})

    tally, _, seen = _classify(monkeypatch, _flaky, 6)

    assert len(seen) == 6 and tally.stopped is None and tally.classified == 3 and tally.failed == 3


def test_connection_repr_hides_secret() -> None:
    connection = AiConnection(family="litellm_usage", values={"base_url": "https://x.example", "virtual_key": KEY})
    assert KEY not in repr(connection)
