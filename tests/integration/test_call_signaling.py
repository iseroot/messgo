import pytest
from httpx import AsyncClient

from tests.conftest import auth_headers


async def _register(client: AsyncClient, username: str, invite_code: str):
    response = await client.post(
        "/api/auth/register",
        json={
            "username": username,
            "display_name": username.capitalize(),
            "password": "very-strong-password",
            "invite_code": invite_code,
        },
    )
    assert response.status_code == 200


@pytest.mark.anyio
async def test_call_start_signal_and_status(client: AsyncClient):
    await _register(client, "owner", "TEST-INVITE")

    invite_response = await client.post(
        "/api/auth/invites",
        headers=await auth_headers(client),
        json={"code": "CALL-INVITE", "ttl_hours": 24, "max_uses": 2},
    )
    assert invite_response.status_code == 200

    await client.post("/api/auth/logout")
    await _register(client, "bob", "CALL-INVITE")
    await client.post("/api/auth/logout")

    await client.post(
        "/api/auth/login",
        json={"username": "owner", "password": "very-strong-password"},
    )

    chat_response = await client.post(
        "/api/chats",
        headers=await auth_headers(client),
        json={"type": "direct", "peer_id": 2},
    )
    chat_id = chat_response.json()["id"]

    call_response = await client.post(
        "/api/calls/start",
        headers=await auth_headers(client),
        json={"chat_id": chat_id, "to_user_id": 2},
    )
    assert call_response.status_code == 200
    call_id = call_response.json()["call_id"]

    signal_response = await client.post(
        "/api/calls/signal",
        headers=await auth_headers(client),
        json={
            "call_id": call_id,
            "to_user_id": 2,
            "type": "offer",
            "payload": "{\"sdp\":\"x\"}",
        },
    )
    assert signal_response.status_code == 200

    status_response = await client.post(
        f"/api/calls/{call_id}/status",
        headers=await auth_headers(client),
        json={"status": "ended"},
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "ended"
