from __future__ import annotations

import pytest

from app.core.config import Settings
from app.core.security import hash_token, new_session_token, session_csrf_token, tokens_match
from app.domain.identity.errors import PasswordPolicyError
from app.domain.identity.passwords import (
    MAX_PASSWORD_LENGTH,
    check_policy,
    common_passwords,
    hash_password,
    is_common,
    verify_password,
)


def test_hash_is_argon2id_and_salted() -> None:
    first = hash_password("correcto-caballo-bateria")
    second = hash_password("correcto-caballo-bateria")

    assert first.startswith("$argon2id$")
    assert first != second
    assert "correcto-caballo-bateria" not in first


def test_verify_accepts_right_and_rejects_wrong_password() -> None:
    stored = hash_password("correcto-caballo-bateria")

    assert verify_password("correcto-caballo-bateria", stored) == (True, None)
    assert verify_password("incorrecto", stored)[0] is False


@pytest.mark.parametrize(
    ("password", "fragment"),
    [
        ("corta", "al menos 12"),
        ("x" * (MAX_PASSWORD_LENGTH + 1), "superar"),
        ("Usuario-Largo1", "nombre de usuario"),
        ("Password1234!", "demasiado común"),
    ],
)
def test_policy_rejects(password: str, fragment: str) -> None:
    with pytest.raises(PasswordPolicyError) as info:
        check_policy(password, username="usuario-largo1", min_length=12)

    assert fragment in (info.value.detail or "")


def test_policy_accepts_valid_password() -> None:
    check_policy("una-frase-de-paso-larga", username="ana", min_length=12)


def test_common_list_is_loaded_without_header_lines() -> None:
    passwords = common_passwords()

    assert len(passwords) >= 10_000
    assert "password" in passwords
    assert not any(p.startswith("#") for p in passwords)


@pytest.mark.parametrize(
    ("password", "common"),
    [
        ("password", True),
        ("PASSWORD", True),
        ("Password1234!", True),
        ("2024dragon2024", True),
        ("una-frase-de-paso-larga", False),
        ("1234ab!!", False),  # núcleo de menos de 4 caracteres: solo cuenta la contraseña completa
    ],
)
def test_is_common_checks_password_and_its_core(password: str, common: bool) -> None:
    assert is_common(password) is common


def test_session_token_is_256_bits_and_only_hash_is_stored() -> None:
    token = new_session_token()

    assert len(token) >= 43
    assert hash_token(token) != token
    assert len(hash_token(token)) == 64


def test_csrf_token_is_bound_to_session_and_key() -> None:
    a = Settings(environment="test", app_secret_key="clave-a")  # type: ignore[arg-type]
    b = Settings(environment="test", app_secret_key="clave-b")  # type: ignore[arg-type]

    assert session_csrf_token(a, "s1") == session_csrf_token(a, "s1")
    assert session_csrf_token(a, "s1") != session_csrf_token(a, "s2")
    assert session_csrf_token(a, "s1") != session_csrf_token(b, "s1")
    assert tokens_match("abc", "abc")
    assert not tokens_match("abc", "abd")


def test_cookie_secure_and_host_prefix_except_in_development() -> None:
    test = Settings(environment="test")
    dev = Settings(environment="development")

    assert test.cookie_secure
    assert (test.session_cookie, test.csrf_cookie) == ("__Host-dow_session", "__Host-dow_csrf")
    assert not dev.cookie_secure
    assert (dev.session_cookie, dev.csrf_cookie) == ("dow_session", "dow_csrf")
