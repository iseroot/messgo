from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import get_settings

_PASSWORD_HASHER = PasswordHasher()


class TokenError(Exception):
    """Ошибка проверки токена."""


def hash_password(password: str) -> str:
    """Хеширует пароль пользователя."""

    return _PASSWORD_HASHER.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Проверяет пароль по хешу."""

    try:
        return _PASSWORD_HASHER.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def build_access_token(user_id: int) -> str:
    """Создаёт короткоживущий access token."""

    settings = get_settings()
    expires_at = datetime.now(tz=UTC) + timedelta(minutes=settings.access_token_ttl_minutes)
    payload = {
        "sub": str(user_id),
        "scope": "access",
        "exp": expires_at,
        "iat": datetime.now(tz=UTC),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def build_refresh_token(user_id: int, session_id: int) -> str:
    """Создаёт refresh token для сессии устройства."""

    settings = get_settings()
    expires_at = datetime.now(tz=UTC) + timedelta(days=settings.refresh_token_ttl_days)
    payload = {
        "sub": str(user_id),
        "sid": str(session_id),
        "scope": "refresh",
        "nonce": token_urlsafe(12),
        "exp": expires_at,
        "iat": datetime.now(tz=UTC),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str, expected_scope: str) -> dict:
    """Проверяет JWT и возвращает payload."""

    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as error:
        raise TokenError("Невалидный токен") from error

    if payload.get("scope") != expected_scope:
        raise TokenError("Неверная область токена")

    return payload


def hash_refresh_token(refresh_token: str) -> str:
    """Возвращает SHA-256 хеш refresh token."""

    return sha256(refresh_token.encode("utf-8")).hexdigest()
