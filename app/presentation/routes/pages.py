from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.security import TokenError, decode_token
from app.infrastructure.repositories import ChatRepository, MessageRepository, UserRepository
from app.presentation.deps import ACCESS_COOKIE_NAME, get_db_session

router = APIRouter(tags=["pages"])


def _get_user_id_optional(token: str | None) -> int | None:
    if token is None:
        return None
    try:
        payload = decode_token(token=token, expected_scope="access")
    except TokenError:
        return None
    return int(payload["sub"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Простой endpoint для health-check."""

    return {"status": "ok"}


@router.get("/")
async def index(
    request: Request,
    token: str | None = Cookie(default=None, alias=ACCESS_COOKIE_NAME),
):
    """Главная страница: логин или редирект в приложение."""

    user_id = _get_user_id_optional(token)
    if user_id is not None:
        return RedirectResponse(url="/app", status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    templates = request.app.state.templates
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "app_name": "messgo",
        },
    )


@router.get("/app")
async def app_page(
    request: Request,
    db: Session = Depends(get_db_session),
    token: str | None = Cookie(default=None, alias=ACCESS_COOKIE_NAME),
):
    """Основной экран приложения."""

    user_id = _get_user_id_optional(token)
    if user_id is None:
        return RedirectResponse(url="/", status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    user = UserRepository(db).get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")

    chat_repo = ChatRepository(db)
    chats = chat_repo.list_user_chats(user_id)

    templates = request.app.state.templates
    return templates.TemplateResponse(
        "app.html",
        {
            "request": request,
            "user": user,
            "chats": chats,
        },
    )


@router.get("/partials/chats")
async def chats_partial(
    request: Request,
    db: Session = Depends(get_db_session),
    token: str | None = Cookie(default=None, alias=ACCESS_COOKIE_NAME),
):
    """Частичный рендер списка чатов для HTMX."""

    user_id = _get_user_id_optional(token)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется авторизация")

    chats = ChatRepository(db).list_user_chats(user_id)
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "partials/chat_list.html",
        {
            "request": request,
            "chats": chats,
        },
    )


@router.get("/partials/chats/{chat_id}/messages")
async def messages_partial(
    chat_id: int,
    request: Request,
    db: Session = Depends(get_db_session),
    token: str | None = Cookie(default=None, alias=ACCESS_COOKIE_NAME),
):
    """Частичный рендер списка сообщений для HTMX."""

    user_id = _get_user_id_optional(token)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется авторизация")

    chat_repo = ChatRepository(db)
    if not chat_repo.is_member(chat_id, user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа")

    messages = MessageRepository(db).list_messages(chat_id=chat_id, limit=100, offset=0)
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "partials/messages.html",
        {
            "request": request,
            "messages": messages,
            "chat_id": chat_id,
        },
    )
