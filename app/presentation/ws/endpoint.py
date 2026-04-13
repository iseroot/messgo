from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.application.errors import AppError
from app.application.services.call_service import CallService
from app.core.security import TokenError, decode_token
from app.domain.enums import PresenceStatus
from app.infrastructure import db as db_module
from app.infrastructure.repositories import CallRepository, ChatRepository, UserRepository
from app.presentation.deps import ACCESS_COOKIE_NAME
from app.presentation.ws.manager import ws_manager

router = APIRouter(tags=["ws"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Основной WebSocket для presence и signaling."""

    token = websocket.cookies.get(ACCESS_COOKIE_NAME)
    if token is None:
        await websocket.close(code=4401)
        return

    try:
        payload = decode_token(token, expected_scope="access")
    except TokenError:
        await websocket.close(code=4401)
        return

    user_id = int(payload["sub"])
    await ws_manager.connect(user_id, websocket)
    await ws_manager.broadcast_presence(user_id=user_id, status=PresenceStatus.ONLINE)

    db = db_module.SessionLocal()
    chat_repo = ChatRepository(db)
    call_service = CallService(chat_repo=chat_repo, call_repo=CallRepository(db))
    user_repo = UserRepository(db)

    try:
        while True:
            event = await websocket.receive_json()
            event_type = event.get("type")

            if event_type == "heartbeat":
                user_repo.update_last_seen(user_id=user_id, seen_at=datetime.now(tz=UTC))
                await websocket.send_json({"type": "heartbeat:ack"})
                continue

            if event_type == "call:start":
                call = call_service.start_call(
                    chat_id=int(event["chat_id"]),
                    initiator_id=user_id,
                    to_user_id=int(event["to_user_id"]),
                )
                payload = {
                    "type": "call:ringing",
                    "call_id": call.id,
                    "chat_id": call.chat_id,
                    "from_user_id": user_id,
                }
                await ws_manager.send_to_user(user_id=int(event["to_user_id"]), payload=payload)
                await websocket.send_json(payload)
                continue

            if event_type == "call:signal":
                call_service.add_signal(
                    call_id=int(event["call_id"]),
                    from_user_id=user_id,
                    to_user_id=int(event["to_user_id"]),
                    event_type=str(event["signal_type"]),
                    payload=str(event["payload"]),
                )
                await ws_manager.send_to_user(
                    user_id=int(event["to_user_id"]),
                    payload={
                        "type": "call:signal",
                        "call_id": int(event["call_id"]),
                        "from_user_id": user_id,
                        "signal_type": event["signal_type"],
                        "payload": event["payload"],
                    },
                )
                continue

            if event_type == "call:status":
                call = call_service.set_status(
                    call_id=int(event["call_id"]),
                    user_id=user_id,
                    status=str(event["status"]),
                )
                member_ids = [member.user_id for member in chat_repo.list_members(call.chat_id)]
                await ws_manager.broadcast_to_users(
                    user_ids=member_ids,
                    payload={
                        "type": "call:status",
                        "call_id": call.id,
                        "status": call.status,
                        "updated_by": user_id,
                    },
                )
                continue

            await websocket.send_json({"type": "error", "message": "Неизвестный тип события"})

    except WebSocketDisconnect:
        pass
    except AppError as error:
        await websocket.send_json({"type": "error", "message": str(error)})
    finally:
        db.close()
        await ws_manager.disconnect(user_id=user_id, websocket=websocket)
        await ws_manager.broadcast_presence(user_id=user_id, status=PresenceStatus.OFFLINE)
