from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.application.errors import AppError
from app.application.services.call_service import CallService
from app.application.services.chat_service import ChatService
from app.application.services.message_service import MessageService
from app.presentation.deps import (
    enforce_csrf,
    get_call_service,
    get_chat_service,
    get_current_user_id,
    get_message_service,
)
from app.presentation.schemas import (
    CallSignalRequest,
    CallStartRequest,
    CallStatusRequest,
    ChatCreateRequest,
    MessageCreateRequest,
)
from app.presentation.ws.manager import ws_manager

router = APIRouter(prefix="/api", tags=["chat"])


@router.get("/chats")
async def list_chats(
    user_id: int = Depends(get_current_user_id),
    chat_service: ChatService = Depends(get_chat_service),
):
    """Возвращает список чатов текущего пользователя."""

    chats = chat_service.list_user_chats(user_id=user_id)
    return [
        {
            "id": chat.id,
            "type": chat.type,
            "title": chat.title,
            "created_at": chat.created_at,
        }
        for chat in chats
    ]


@router.post("/chats")
async def create_chat(
    payload: ChatCreateRequest,
    request: Request,
    user_id: int = Depends(get_current_user_id),
    chat_service: ChatService = Depends(get_chat_service),
):
    """Создаёт direct/group чат."""

    enforce_csrf(request)
    try:
        if payload.type == "direct":
            if payload.peer_id is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="peer_id обязателен")
            chat = chat_service.create_direct_chat(owner_id=user_id, peer_id=payload.peer_id)
        else:
            chat = chat_service.create_group_chat(
                owner_id=user_id,
                title=payload.title or "Группа",
                member_ids=payload.member_ids,
            )
    except AppError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error

    return {
        "id": chat.id,
        "type": chat.type,
        "title": chat.title,
        "created_at": chat.created_at,
    }


@router.get("/chats/{chat_id}/messages")
async def list_messages(
    chat_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user_id: int = Depends(get_current_user_id),
    message_service: MessageService = Depends(get_message_service),
):
    """Возвращает порцию сообщений чата."""

    try:
        messages = message_service.list_messages(chat_id=chat_id, user_id=user_id, limit=limit, offset=offset)
    except AppError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error

    return [
        {
            "id": message.id,
            "chat_id": message.chat_id,
            "sender_id": message.sender_id,
            "text": message.text,
            "status": message.status,
            "created_at": message.created_at,
        }
        for message in messages
    ]


@router.post("/chats/{chat_id}/messages")
async def send_message(
    chat_id: int,
    payload: MessageCreateRequest,
    request: Request,
    user_id: int = Depends(get_current_user_id),
    message_service: MessageService = Depends(get_message_service),
):
    """Отправляет сообщение в чат."""

    enforce_csrf(request)
    try:
        result = message_service.send_text_message(
            chat_id=chat_id,
            sender_id=user_id,
            text=payload.text,
            reply_to_message_id=payload.reply_to_message_id,
            online_user_ids=ws_manager.get_online_user_ids(),
        )
    except AppError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error

    event = {
        "type": "message:new",
        "message": {
            "id": result.message_id,
            "chat_id": result.chat_id,
            "sender_id": result.sender_id,
            "text": result.text,
            "status": result.status,
        },
    }
    await ws_manager.broadcast_to_users(user_ids=result.member_ids, payload=event)

    return event["message"]


@router.post("/messages/{message_id}/read")
async def mark_message_read(
    message_id: int,
    request: Request,
    user_id: int = Depends(get_current_user_id),
    message_service: MessageService = Depends(get_message_service),
):
    """Отмечает сообщение как прочитанное."""

    enforce_csrf(request)
    try:
        message = message_service.mark_read(message_id=message_id, user_id=user_id)
    except AppError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error

    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сообщение не найдено")

    await ws_manager.broadcast_to_users(
        user_ids=list(ws_manager.get_online_user_ids()),
        payload={
            "type": "message:read",
            "message_id": message.id,
            "chat_id": message.chat_id,
            "read_by": user_id,
        },
    )

    return {"ok": True}


@router.post("/calls/start")
async def start_call(
    payload: CallStartRequest,
    request: Request,
    user_id: int = Depends(get_current_user_id),
    call_service: CallService = Depends(get_call_service),
):
    """Создаёт звонок и отправляет событие входящего вызова."""

    enforce_csrf(request)
    try:
        call = call_service.start_call(
            chat_id=payload.chat_id,
            initiator_id=user_id,
            to_user_id=payload.to_user_id,
        )
    except AppError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error

    await ws_manager.send_to_user(
        user_id=payload.to_user_id,
        payload={
            "type": "call:ringing",
            "call_id": call.id,
            "chat_id": call.chat_id,
            "from_user_id": user_id,
        },
    )

    return {"ok": True, "call_id": call.id}


@router.post("/calls/signal")
async def signal_call(
    payload: CallSignalRequest,
    request: Request,
    user_id: int = Depends(get_current_user_id),
    call_service: CallService = Depends(get_call_service),
):
    """Передаёт сигналинг между участниками звонка."""

    enforce_csrf(request)
    try:
        call_service.add_signal(
            call_id=payload.call_id,
            from_user_id=user_id,
            to_user_id=payload.to_user_id,
            event_type=payload.type,
            payload=payload.payload,
        )
    except AppError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error

    await ws_manager.send_to_user(
        user_id=payload.to_user_id,
        payload={
            "type": "call:signal",
            "call_id": payload.call_id,
            "from_user_id": user_id,
            "signal_type": payload.type,
            "payload": payload.payload,
        },
    )

    return {"ok": True}


@router.post("/calls/{call_id}/status")
async def update_call_status(
    call_id: int,
    payload: CallStatusRequest,
    request: Request,
    user_id: int = Depends(get_current_user_id),
    call_service: CallService = Depends(get_call_service),
):
    """Обновляет статус звонка."""

    enforce_csrf(request)
    try:
        call = call_service.set_status(call_id=call_id, user_id=user_id, status=payload.status)
    except AppError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error

    await ws_manager.broadcast_to_users(
        user_ids=list(ws_manager.get_online_user_ids()),
        payload={
            "type": "call:status",
            "call_id": call.id,
            "status": call.status,
            "updated_by": user_id,
        },
    )

    return {"ok": True, "status": call.status}
