from __future__ import annotations

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.application.errors import AuthError
from app.application.services.auth_service import AuthService
from app.application.services.call_service import CallService
from app.application.services.chat_service import ChatService
from app.application.services.message_service import MessageService
from app.core.rate_limit import InMemoryRateLimiter
from app.core.security import TokenError, decode_token
from app.infrastructure import db as db_module
from app.infrastructure.repositories import (
    CallRepository,
    ChatRepository,
    InviteRepository,
    MessageRepository,
    SessionRepository,
    UserRepository,
)

ACCESS_COOKIE_NAME = "messgo_access_token"
REFRESH_COOKIE_NAME = "messgo_refresh_token"
CSRF_COOKIE_NAME = "messgo_csrf_token"

rate_limiter = InMemoryRateLimiter()


async def get_db_session():
    """Создаёт сессию БД для async endpoint."""

    db = db_module.SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_user_repo(db: Session = Depends(get_db_session)) -> UserRepository:
    return UserRepository(db)


async def get_auth_service(db: Session = Depends(get_db_session)) -> AuthService:
    return AuthService(
        user_repo=UserRepository(db),
        invite_repo=InviteRepository(db),
        session_repo=SessionRepository(db),
    )


async def get_chat_service(db: Session = Depends(get_db_session)) -> ChatService:
    return ChatService(chat_repo=ChatRepository(db), user_repo=UserRepository(db))


async def get_message_service(db: Session = Depends(get_db_session)) -> MessageService:
    return MessageService(chat_repo=ChatRepository(db), message_repo=MessageRepository(db))


async def get_call_service(db: Session = Depends(get_db_session)) -> CallService:
    return CallService(chat_repo=ChatRepository(db), call_repo=CallRepository(db))


async def get_current_user_id(
    token: str | None = Cookie(default=None, alias=ACCESS_COOKIE_NAME),
) -> int:
    """Возвращает id пользователя из access cookie."""

    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется авторизация")

    try:
        payload = decode_token(token=token, expected_scope="access")
    except TokenError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Невалидный токен") from error

    return int(payload["sub"])


def get_client_ip(request: Request) -> str:
    """Возвращает IP клиента с учётом proxy заголовков."""

    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    client = request.client
    return client.host if client else "unknown"


def get_user_agent(request: Request) -> str:
    """Возвращает user-agent клиента."""

    return request.headers.get("user-agent", "unknown")


def enforce_csrf(request: Request) -> None:
    """Проверяет CSRF токен для мутаций."""

    csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME)
    csrf_header = request.headers.get("x-csrf-token")
    if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token mismatch")


def assert_rate_limit(key: str, limit: int, window_seconds: int) -> None:
    """Выбрасывает ошибку при превышении лимита."""

    if not rate_limiter.allow(key=key, limit=limit, window_seconds=window_seconds):
        raise AuthError("Слишком много попыток, повторите позже")
