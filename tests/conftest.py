from __future__ import annotations

import importlib

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def app_instance(tmp_path, monkeypatch) -> FastAPI:
    db_path = tmp_path / "test.db"
    database_url = f"sqlite:///{db_path}"

    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("JWT_SECRET", "test-secret-123456789012345678901234567890")
    monkeypatch.setenv("BOOTSTRAP_INVITE_CODE", "TEST-INVITE")
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("ENVIRONMENT", "test")

    from app.core.config import get_settings

    get_settings.cache_clear()

    import app.infrastructure.db as db_module

    db_module.configure_engine(database_url)
    db_module.init_db()

    import app.main as main_module

    importlib.reload(main_module)
    import app.presentation.deps as deps_module

    deps_module.rate_limiter.reset()
    test_app = main_module.create_app()

    return test_app


@pytest.fixture
async def client(app_instance: FastAPI):
    await app_instance.router.startup()
    transport = ASGITransport(app=app_instance)
    async with AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client
    await app_instance.router.shutdown()


@pytest.fixture
async def auth_client(client: AsyncClient):
    response = await client.post(
        "/api/auth/register",
        json={
            "username": "alice",
            "display_name": "Alice",
            "password": "very-strong-password",
            "invite_code": "TEST-INVITE",
        },
    )
    assert response.status_code == 200
    return client


async def get_csrf(client: AsyncClient) -> str:
    response = await client.get("/api/auth/csrf")
    assert response.status_code == 200
    payload = response.json()
    token = payload.get("csrf_token")
    assert token
    return token


async def auth_headers(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": await get_csrf(client)}
