from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import UTC, datetime

from fastapi import WebSocket

from app.domain.enums import PresenceStatus


class WebSocketManager:
    """Менеджер активных WebSocket-соединений."""

    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = defaultdict(set)
        self._last_seen: dict[int, datetime] = {}
        self._lock = asyncio.Lock()

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[user_id].add(websocket)
            self._last_seen[user_id] = datetime.now(tz=UTC)

    async def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        async with self._lock:
            sockets = self._connections.get(user_id)
            if not sockets:
                return
            sockets.discard(websocket)
            if not sockets:
                self._connections.pop(user_id, None)
                self._last_seen[user_id] = datetime.now(tz=UTC)

    def get_online_user_ids(self) -> set[int]:
        return {user_id for user_id, sockets in self._connections.items() if sockets}

    async def send_to_user(self, user_id: int, payload: dict) -> None:
        sockets = list(self._connections.get(user_id, set()))
        for socket in sockets:
            await socket.send_json(payload)

    async def broadcast_to_users(self, user_ids: list[int], payload: dict) -> None:
        for user_id in user_ids:
            await self.send_to_user(user_id=user_id, payload=payload)

    async def broadcast_presence(self, user_id: int, status: PresenceStatus) -> None:
        payload = {
            "type": "presence:update",
            "user_id": user_id,
            "status": status.value,
            "updated_at": datetime.now(tz=UTC).isoformat(),
        }
        recipients = list(self.get_online_user_ids())
        await self.broadcast_to_users(recipients, payload)


ws_manager = WebSocketManager()
