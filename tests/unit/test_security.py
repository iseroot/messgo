from app.core.config import get_settings
from app.core.security import (
    TokenError,
    build_access_token,
    build_refresh_token,
    decode_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)


def test_password_hash_roundtrip():
    password_hash = hash_password("strong-pass")
    assert verify_password("strong-pass", password_hash)
    assert not verify_password("wrong-pass", password_hash)


def test_access_token_roundtrip(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "unit-secret-123456789012345678901234567890")
    get_settings.cache_clear()

    token = build_access_token(user_id=42)
    payload = decode_token(token, expected_scope="access")

    assert payload["sub"] == "42"
    assert payload["scope"] == "access"


def test_refresh_token_scope_validation(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "unit-secret-123456789012345678901234567890")
    get_settings.cache_clear()

    token = build_refresh_token(user_id=5, session_id=9)
    payload = decode_token(token, expected_scope="refresh")
    assert payload["sid"] == "9"

    try:
        decode_token(token, expected_scope="access")
    except TokenError:
        assert True
    else:
        raise AssertionError("Ожидалась ошибка проверки scope")


def test_refresh_hash_is_deterministic():
    first = hash_refresh_token("abc")
    second = hash_refresh_token("abc")
    assert first == second
