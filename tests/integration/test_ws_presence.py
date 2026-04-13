import pytest

from app.domain.enums import PresenceStatus
from app.presentation.ws.manager import WebSocketManager


class FakeWebSocket:
    def __init__(self):
        self.accepted = False
        self.sent = []

    async def accept(self):
        self.accepted = True

    async def send_json(self, payload):
        self.sent.append(payload)


@pytest.mark.anyio
async def test_ws_manager_presence_flow():
    manager = WebSocketManager()
    socket = FakeWebSocket()

    await manager.connect(user_id=1, websocket=socket)
    assert socket.accepted
    assert manager.get_online_user_ids() == {1}

    await manager.broadcast_presence(user_id=1, status=PresenceStatus.ONLINE)
    assert socket.sent[-1]["type"] == "presence:update"
    assert socket.sent[-1]["status"] == "online"

    await manager.disconnect(user_id=1, websocket=socket)
    assert manager.get_online_user_ids() == set()
