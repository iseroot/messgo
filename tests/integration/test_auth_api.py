import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers


@pytest.mark.anyio
async def test_register_login_me_refresh_logout(client: AsyncClient):
    register_response = await client.post(
        "/api/auth/register",
        json={
            "username": "alice",
            "display_name": "Alice",
            "password": "very-strong-password",
            "invite_code": "TEST-INVITE",
        },
    )
    assert register_response.status_code == 200

    me_response = await client.get("/api/auth/me")
    assert me_response.status_code == 200
    assert me_response.json()["username"] == "alice"

    refresh_response = await client.post("/api/auth/refresh")
    assert refresh_response.status_code == 200

    logout_response = await client.post("/api/auth/logout")
    assert logout_response.status_code == 200

    me_after_logout = await client.get("/api/auth/me")
    assert me_after_logout.status_code == 401

    login_response = await client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "very-strong-password"},
    )
    assert login_response.status_code == 200


@pytest.mark.anyio
async def test_create_invite(client: AsyncClient):
    await client.post(
        "/api/auth/register",
        json={
            "username": "owner",
            "display_name": "Owner",
            "password": "very-strong-password",
            "invite_code": "TEST-INVITE",
        },
    )

    response = await client.post(
        "/api/auth/invites",
        headers=await auth_headers(client),
        json={"code": "TEAM-INVITE", "ttl_hours": 24, "max_uses": 5},
    )
    assert response.status_code == 200
    assert response.json()["code"] == "TEAM-INVITE"
