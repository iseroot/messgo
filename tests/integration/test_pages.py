import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_index_and_health(client: AsyncClient):
    health = await client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    index = await client.get("/")
    assert index.status_code == 200
    assert "Регистрация по инвайту" in index.text


@pytest.mark.anyio
async def test_app_and_partials(client: AsyncClient):
    register = await client.post(
        "/api/auth/register",
        json={
            "username": "alice",
            "display_name": "Alice",
            "password": "very-strong-password",
            "invite_code": "TEST-INVITE",
        },
    )
    assert register.status_code == 200

    app_page = await client.get("/app")
    assert app_page.status_code == 200
    assert "Выберите чат" in app_page.text

    partial_chats = await client.get("/partials/chats")
    assert partial_chats.status_code == 200

    csrf = (await client.get("/api/auth/csrf")).json()["csrf_token"]
    group_response = await client.post(
        "/api/chats",
        headers={"X-CSRF-Token": csrf},
        json={"type": "group", "title": "Команда", "member_ids": []},
    )
    assert group_response.status_code == 200
    chat_id = group_response.json()["id"]

    partial_messages = await client.get(f"/partials/chats/{chat_id}/messages")
    assert partial_messages.status_code == 200
