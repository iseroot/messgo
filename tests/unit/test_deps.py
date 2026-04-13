import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.application.errors import AuthError
from app.presentation.deps import (
    assert_rate_limit,
    enforce_csrf,
    get_client_ip,
    get_current_user_id,
    rate_limiter,
)


def _build_request(headers: list[tuple[bytes, bytes]], client: tuple[str, int] = ("127.0.0.1", 1000)) -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/",
        "headers": headers,
        "client": client,
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(scope, receive)


@pytest.mark.anyio
async def test_get_current_user_id_invalid_token():
    with pytest.raises(HTTPException):
        await get_current_user_id(token="broken-token")


def test_get_client_ip_uses_forwarded_header():
    request = _build_request(headers=[(b"x-forwarded-for", b"1.2.3.4, 5.6.7.8")])
    assert get_client_ip(request) == "1.2.3.4"


def test_enforce_csrf_raises_on_mismatch():
    request = _build_request(
        headers=[
            (b"cookie", b"messgo_csrf_token=aaa"),
            (b"x-csrf-token", b"bbb"),
        ]
    )
    with pytest.raises(HTTPException):
        enforce_csrf(request)


def test_assert_rate_limit_raises():
    rate_limiter.reset()
    assert_rate_limit(key="unit-limit", limit=1, window_seconds=60)
    with pytest.raises(AuthError):
        assert_rate_limit(key="unit-limit", limit=1, window_seconds=60)
