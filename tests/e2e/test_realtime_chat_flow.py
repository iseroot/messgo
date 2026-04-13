import pytest
from httpx import ASGITransport, AsyncClient

from tests.conftest import auth_headers


@pytest.mark.anyio
async def test_full_user_to_user_flow(app_instance):
    owner_transport = ASGITransport(app=app_instance)
    bob_transport = ASGITransport(app=app_instance)

    async with AsyncClient(transport=owner_transport, base_url="http://testserver") as owner_client, AsyncClient(
        transport=bob_transport, base_url="http://testserver"
    ) as bob_client:
        owner_register = await owner_client.post(
            "/api/auth/register",
            json={
                "username": "owner",
                "display_name": "Owner",
                "password": "very-strong-password",
                "invite_code": "TEST-INVITE",
            },
        )
        assert owner_register.status_code == 200

        create_invite = await owner_client.post(
            "/api/auth/invites",
            headers=await auth_headers(owner_client),
            json={"code": "E2E-BOB", "ttl_hours": 24, "max_uses": 2},
        )
        assert create_invite.status_code == 200

        bob_register = await bob_client.post(
            "/api/auth/register",
            json={
                "username": "bob",
                "display_name": "Bob",
                "password": "very-strong-password",
                "invite_code": "E2E-BOB",
            },
        )
        assert bob_register.status_code == 200

        create_chat = await owner_client.post(
            "/api/chats",
            headers=await auth_headers(owner_client),
            json={"type": "direct", "peer_id": 2},
        )
        assert create_chat.status_code == 200
        chat_id = create_chat.json()["id"]

        send_message = await owner_client.post(
            f"/api/chats/{chat_id}/messages",
            headers=await auth_headers(owner_client),
            json={"text": "Привет, Bob"},
        )
        assert send_message.status_code == 200

        start_call = await owner_client.post(
            "/api/calls/start",
            headers=await auth_headers(owner_client),
            json={"chat_id": chat_id, "to_user_id": 2},
        )
        assert start_call.status_code == 200
        call_id = start_call.json()["call_id"]

        offer_signal = await owner_client.post(
            "/api/calls/signal",
            headers=await auth_headers(owner_client),
            json={
                "call_id": call_id,
                "to_user_id": 2,
                "type": "offer",
                "payload": "{\"sdp\":\"x\"}",
            },
        )
        assert offer_signal.status_code == 200

        end_call = await owner_client.post(
            f"/api/calls/{call_id}/status",
            headers=await auth_headers(owner_client),
            json={"status": "ended"},
        )
        assert end_call.status_code == 200

        bob_messages = await bob_client.get(f"/api/chats/{chat_id}/messages")
        assert bob_messages.status_code == 200
        assert len(bob_messages.json()) == 1
        assert bob_messages.json()[0]["text"] == "Привет, Bob"
