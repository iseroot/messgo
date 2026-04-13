from __future__ import annotations

from secrets import token_urlsafe

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.application.errors import AppError, AuthError
from app.application.services.auth_service import AuthService
from app.core.config import get_settings
from app.core.security import decode_token
from app.infrastructure.repositories import UserRepository
from app.presentation.deps import (
    ACCESS_COOKIE_NAME,
    CSRF_COOKIE_NAME,
    REFRESH_COOKIE_NAME,
    assert_rate_limit,
    enforce_csrf,
    get_auth_service,
    get_client_ip,
    get_current_user_id,
    get_db_session,
    get_user_agent,
)
from app.presentation.schemas import InviteCreateRequest, LoginRequest, RegisterRequest

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> str:
    """Устанавливает auth cookies и возвращает CSRF токен."""

    csrf_token = token_urlsafe(24)
    common_options = {
        "secure": settings.cookie_secure,
        "samesite": "lax",
        "domain": settings.cookie_domain,
    }
    response.set_cookie(
        ACCESS_COOKIE_NAME,
        access_token,
        httponly=True,
        max_age=settings.access_token_ttl_minutes * 60,
        **common_options,
    )
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        refresh_token,
        httponly=True,
        max_age=settings.refresh_token_ttl_days * 24 * 3600,
        **common_options,
    )
    response.set_cookie(
        CSRF_COOKIE_NAME,
        csrf_token,
        httponly=False,
        max_age=settings.refresh_token_ttl_days * 24 * 3600,
        **common_options,
    )
    return csrf_token


def _clear_auth_cookies(response: Response) -> None:
    """Очищает auth cookies."""

    response.delete_cookie(ACCESS_COOKIE_NAME, domain=settings.cookie_domain)
    response.delete_cookie(REFRESH_COOKIE_NAME, domain=settings.cookie_domain)
    response.delete_cookie(CSRF_COOKIE_NAME, domain=settings.cookie_domain)


@router.post("/register")
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    service: AuthService = Depends(get_auth_service),
):
    """Регистрирует пользователя по инвайту."""

    ip = get_client_ip(request)
    assert_rate_limit(key=f"register:{ip}", limit=10, window_seconds=3600)

    try:
        tokens = service.register(
            username=payload.username,
            display_name=payload.display_name,
            password=payload.password,
            invite_code=payload.invite_code,
            user_agent=get_user_agent(request),
            ip=ip,
        )
    except AppError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error

    csrf_token = _set_auth_cookies(response, tokens.access_token, tokens.refresh_token)
    return {"ok": True, "user_id": tokens.user_id, "csrf_token": csrf_token}


@router.post("/login")
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    service: AuthService = Depends(get_auth_service),
):
    """Выполняет вход пользователя."""

    ip = get_client_ip(request)
    assert_rate_limit(key=f"login:{ip}", limit=20, window_seconds=3600)

    try:
        tokens = service.login(
            username=payload.username,
            password=payload.password,
            user_agent=get_user_agent(request),
            ip=ip,
        )
    except AuthError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)) from error

    csrf_token = _set_auth_cookies(response, tokens.access_token, tokens.refresh_token)
    return {"ok": True, "user_id": tokens.user_id, "csrf_token": csrf_token}


@router.post("/refresh")
async def refresh(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
    service: AuthService = Depends(get_auth_service),
):
    """Обновляет access token по refresh token."""

    if refresh_token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Нет refresh token")

    try:
        tokens = service.refresh(
            refresh_token=refresh_token,
            user_agent=get_user_agent(request),
            ip=get_client_ip(request),
        )
    except AppError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)) from error

    csrf_token = _set_auth_cookies(response, tokens.access_token, tokens.refresh_token)
    return {"ok": True, "csrf_token": csrf_token}


@router.post("/logout")
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
    service: AuthService = Depends(get_auth_service),
):
    """Завершает текущую сессию пользователя."""

    if refresh_token:
        service.logout(refresh_token)
    _clear_auth_cookies(response)
    return {"ok": True}


@router.post("/logout-all")
async def logout_all(
    request: Request,
    response: Response,
    user_id: int = Depends(get_current_user_id),
    service: AuthService = Depends(get_auth_service),
):
    """Завершает все сессии текущего пользователя."""

    enforce_csrf(request)
    service.logout_all(user_id)
    _clear_auth_cookies(response)
    return {"ok": True}


@router.post("/invites")
async def create_invite(
    payload: InviteCreateRequest,
    request: Request,
    user_id: int = Depends(get_current_user_id),
    service: AuthService = Depends(get_auth_service),
):
    """Создаёт новый инвайт для регистрации."""

    enforce_csrf(request)
    assert_rate_limit(key=f"invite:{user_id}", limit=20, window_seconds=3600)

    try:
        invite = service.create_invite(
            code=payload.code,
            created_by=user_id,
            ttl_hours=payload.ttl_hours,
            max_uses=payload.max_uses,
        )
    except AppError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error

    return {
        "ok": True,
        "code": invite.code,
        "expires_at": invite.expires_at,
        "max_uses": invite.max_uses,
        "used_count": invite.used_count,
    }


@router.get("/me")
async def me(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db_session),
):
    """Возвращает профиль текущего пользователя."""

    user = UserRepository(db).get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")

    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "last_seen_at": user.last_seen_at,
    }


@router.post("/bootstrap-invite")
async def bootstrap_invite(
    request: Request,
    service: AuthService = Depends(get_auth_service),
):
    """Создаёт стартовый инвайт, если его нет."""

    client_ip = get_client_ip(request)
    if client_ip not in {"127.0.0.1", "::1", "unknown"}:
        token = request.headers.get("x-admin-token")
        if token != settings.jwt_secret:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")

    service.ensure_bootstrap_invite(
        code=settings.bootstrap_invite_code,
        ttl_hours=settings.invite_default_ttl_hours,
        max_uses=settings.invite_default_limit,
    )
    return {"ok": True, "code": settings.bootstrap_invite_code}


@router.get("/csrf")
async def csrf_token(
    token: str | None = Cookie(default=None, alias=CSRF_COOKIE_NAME),
):
    """Возвращает текущий CSRF токен."""

    return {"csrf_token": token}


@router.get("/token-debug")
async def token_debug(
    token: str | None = Cookie(default=None, alias=ACCESS_COOKIE_NAME),
):
    """Диагностика payload access token в dev среде."""

    if settings.environment != "dev":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Недоступно")
    if token is None:
        return {"payload": None}
    return {"payload": decode_token(token, expected_scope="access")}
