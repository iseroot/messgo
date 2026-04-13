from __future__ import annotations

import pytest
from fastapi import WebSocketDisconnect

from app.core.security import build_access_token, hash_password
from app.domain.enums import CallStatus
from app.infrastructure import db as db_module
from app.infrastructure.repositories import CallRepository, ChatRepository, UserRepository
from app.presentation.ws.endpoint import websocket_endpoint
from app.presentation.ws.manager import ws_manager


class FakeWebSocket:
    def __init__(self, cookies: dict[str, str], events: list[dict]):
        self.cookies = cookies
        self._events = list(events)
        self.sent: list[dict] = []
        self.accepted = False
        self.closed_code = None

    async def accept(self):
        self.accepted = True

    async def close(self, code: int):
        self.closed_code = code

    async def receive_json(self):
        if not self._events:
            raise WebSocketDisconnect(code=1000)
        return self._events.pop(0)

    async def send_json(self, payload):
        self.sent.append(payload)


def _create_direct_chat_pair() -> tuple[int, int, int]:
    session = db_module.SessionLocal()
    try:
        user_repo = UserRepository(session)
        chat_repo = ChatRepository(session)

        user_one = user_repo.create("u1", "User 1", hash_password("very-strong-password"))
        user_two = user_repo.create("u2", "User 2", hash_password("very-strong-password"))

        chat = chat_repo.create_chat(chat_type="direct", title=None, created_by=user_one.id)
        chat_repo.add_member(chat.id, user_one.id, role="owner")
        chat_repo.add_member(chat.id, user_two.id, role="member")

        return user_one.id, user_two.id, chat.id
    finally:
        session.close()


@pytest.mark.anyio
async def test_ws_rejects_without_token(app_instance):
    ws_manager._connections.clear()
    websocket = FakeWebSocket(cookies={}, events=[])

    await websocket_endpoint(websocket)

    assert websocket.closed_code == 4401


@pytest.mark.anyio
async def test_ws_handles_heartbeat_call_start_and_unknown_event(app_instance):
    ws_manager._connections.clear()
    user_id, peer_id, chat_id = _create_direct_chat_pair()
    token = build_access_token(user_id)

    websocket = FakeWebSocket(
        cookies={"messgo_access_token": token},
        events=[
            {"type": "heartbeat"},
            {"type": "call:start", "chat_id": chat_id, "to_user_id": peer_id},
            {"type": "unknown"},
        ],
    )

    await websocket_endpoint(websocket)

    assert websocket.accepted
    assert any(event.get("type") == "heartbeat:ack" for event in websocket.sent)
    assert any(event.get("type") == "call:ringing" for event in websocket.sent)
    assert any(event.get("type") == "error" for event in websocket.sent)


@pytest.mark.anyio
async def test_ws_handles_signal_and_status(app_instance):
    ws_manager._connections.clear()
    user_id, peer_id, chat_id = _create_direct_chat_pair()
    token = build_access_token(user_id)

    db = db_module.SessionLocal()
    try:
        call = CallRepository(db).create_call(chat_id=chat_id, initiator_id=user_id, status=CallStatus.RINGING.value)
    finally:
        db.close()

    websocket = FakeWebSocket(
        cookies={"messgo_access_token": token},
        events=[
            {
                "type": "call:signal",
                "call_id": call.id,
                "to_user_id": peer_id,
                "signal_type": "offer",
                "payload": "{}",
            },
            {"type": "call:status", "call_id": call.id, "status": "ended"},
        ],
    )

    await websocket_endpoint(websocket)

    assert websocket.accepted
    assert any(event.get("type") == "call:status" for event in websocket.sent)


@pytest.mark.anyio
async def test_ws_sends_error_on_app_exception(app_instance):
    ws_manager._connections.clear()
    user_id, peer_id, _chat_id = _create_direct_chat_pair()
    token = build_access_token(user_id)

    websocket = FakeWebSocket(
        cookies={"messgo_access_token": token},
        events=[
            {
                "type": "call:signal",
                "call_id": 999999,
                "to_user_id": peer_id,
                "signal_type": "offer",
                "payload": "{}",
            }
        ],
    )

    await websocket_endpoint(websocket)

    assert any(event.get("type") == "error" for event in websocket.sent)
