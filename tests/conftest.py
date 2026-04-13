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

    # Явно выполняем минимум логики startup, чтобы не зависеть от реализации lifespan в httpx/starlette.
    from app.application.services.auth_service import AuthService
    from app.infrastructure.repositories import InviteRepository, SessionRepository, UserRepository

    db = db_module.SessionLocal()
    try:
        settings = get_settings()
        AuthService(
            user_repo=UserRepository(db),
            invite_repo=InviteRepository(db),
            session_repo=SessionRepository(db),
        ).ensure_bootstrap_invite(
            code=settings.bootstrap_invite_code,
            ttl_hours=settings.invite_default_ttl_hours,
            max_uses=settings.invite_default_limit,
        )
    finally:
        db.close()

    return test_app


@pytest.fixture
async def client(app_instance: FastAPI):
    transport = ASGITransport(app=app_instance)
    async with AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client


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
