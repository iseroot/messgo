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
async def test_chat_and_message_flow(client: AsyncClient):
    await _register(client, "owner", "TEST-INVITE")

    invite_response = await client.post(
        "/api/auth/invites",
        headers=await auth_headers(client),
        json={"code": "BOB-INVITE", "ttl_hours": 24, "max_uses": 2},
    )
    assert invite_response.status_code == 200

    await client.post("/api/auth/logout")

    await _register(client, "bob", "BOB-INVITE")
    await client.post("/api/auth/logout")

    login_owner = await client.post(
        "/api/auth/login",
        json={"username": "owner", "password": "very-strong-password"},
    )
    assert login_owner.status_code == 200

    direct_chat_response = await client.post(
        "/api/chats",
        headers=await auth_headers(client),
        json={"type": "direct", "peer_id": 2},
    )
    assert direct_chat_response.status_code == 200
    chat_id = direct_chat_response.json()["id"]

    send_response = await client.post(
        f"/api/chats/{chat_id}/messages",
        headers=await auth_headers(client),
        json={"text": "Привет, Bob"},
    )
    assert send_response.status_code == 200
    message_id = send_response.json()["id"]

    list_response = await client.get(f"/api/chats/{chat_id}/messages")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    read_response = await client.post(
        f"/api/messages/{message_id}/read", headers=await auth_headers(client)
    )
    assert read_response.status_code == 200


@pytest.mark.anyio
async def test_group_chat_create(client: AsyncClient):
    await _register(client, "owner", "TEST-INVITE")

    group_response = await client.post(
        "/api/chats",
        headers=await auth_headers(client),
        json={"type": "group", "title": "Команда", "member_ids": []},
    )
    assert group_response.status_code == 200

    chats_response = await client.get("/api/chats")
    assert chats_response.status_code == 200
    assert any(chat["type"] == "group" for chat in chats_response.json())
