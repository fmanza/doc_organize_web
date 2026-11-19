"""IA (Fase 8; doc_organize 2.0 en W2) sin red: cifrado MultiFernet, ``hint``, validación de ``base_url`` y
configuración del cliente único (``AiSettings`` por tarea: modelo, clave, reintentos y presupuesto) y del de uso (clave
fuera de la URL) sobre ``httpx.MockTransport``."""

from __future__ import annotations

import asyncio

import httpx
import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr

from app.core import crypto
from app.core.config import Settings
from app.domain.ai.errors import InvalidAiSettingError
from app.domain.ai.settings import hint, validate_base_url
from app.integrations.doc_organize import ai as library_ai
from app.integrations.doc_organize.ai import AiConnection

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


def test_settings_carry_timeout_retries_and_a_model_and_key_per_task() -> None:
    connection = AiConnection(
        family="litellm",
        values={
            "base_url": "https://litellm.example.internal",
            "virtual_key": KEY,
            "model_classify": "clasificador",
            "virtual_key_enrich": "sk-enrich-1111",
            "budget_enrich": "5",
        },
        timeout_s=12.0,
        retries=3,
        budget=7,
    )

    settings = library_ai.ai_settings_for(connection)

    assert (settings.timeout_s, settings.retries, settings.redact_credentials) == (12.0, 3, True)
    assert settings.model_for("classify") == "clasificador" and settings.key_for("classify") == KEY
    assert settings.model_for("enrich") == "doc-organize-enrich" and settings.key_for("enrich") == "sk-enrich-1111"
    assert settings.model_for("taxonomy_design") == "doc-organize-taxonomy-design"
    assert KEY not in repr(settings) and "sk-enrich" not in repr(settings)
    assert library_ai.build_limits(connection, ["classify"]) == {
        "ai_max_failures": library_ai.MAX_CONNECTION_FAILURES,
        "ai_max_documents": 7,
    }
    # Con las dos fases, el menor presupuesto (doc_organize 2.0.0a2 tiene un solo tope que aplica a cada fase).
    assert library_ai.build_limits(connection, ["classify", "enrich"])["ai_max_documents"] == 5
    copilot = library_ai._usage_config(
        AiConnection(family="github_copilot_usage", values={"username": "octo", "pat": KEY}, retries=1)
    )
    assert copilot.retries == 1 and copilot.personal_access_token == KEY


def test_only_the_litellm_family_builds_an_llm_client() -> None:
    with pytest.raises(ValueError):
        library_ai.llm_client(AiConnection(family="litellm_usage", values={}))


def test_legacy_variables_name_their_replacement() -> None:
    """D15: las variables de 1.x se detectan (sin valores) con su equivalente de 2.0."""
    found = library_ai.legacy_env({"DOC_ORGANIZE_LITELLM_TAXONOMY_MANIFEST_DRAFT_MODEL": "x", "OTRA": "y"})
    assert found == {"DOC_ORGANIZE_LITELLM_TAXONOMY_MANIFEST_DRAFT_MODEL": "DOC_ORGANIZE_LITELLM_MODEL_TAXONOMY_DESIGN"}


def test_usage_does_not_put_the_key_in_the_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """L-3e (G37): con 0.14.0 la clave propia ya no va en ``/key/info?key=``."""
    seen: list[httpx.Request] = []

    def _handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"info": {"spend": 1.5}})

    monkeypatch.setattr(library_ai, "_transport", lambda _: httpx.MockTransport(_handle))
    connection = AiConnection(
        family="litellm_usage", values={"base_url": "https://litellm.example.internal", "virtual_key": KEY}
    )

    report = asyncio.run(library_ai.fetch_usage("litellm", connection))

    assert report.items[0].cost_usd == 1.5
    assert KEY not in str(seen[0].url) and seen[0].headers["authorization"] == f"Bearer {KEY}"


def test_connection_repr_hides_secret() -> None:
    connection = AiConnection(family="litellm_usage", values={"base_url": "https://x.example", "virtual_key": KEY})
    assert KEY not in repr(connection)
