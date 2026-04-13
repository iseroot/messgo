from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.application.errors import AuthError, ValidationError
from app.application.ports import InviteRepoPort, SessionRepoPort, UserRepoPort
from app.core.security import (
    build_access_token,
    build_refresh_token,
    decode_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)


@dataclass(slots=True)
class AuthTokens:
    """Пара токенов аутентификации."""

    access_token: str
    refresh_token: str
    user_id: int


class AuthService:
    """Сервис сценариев аутентификации и регистрации."""

    def __init__(
        self,
        user_repo: UserRepoPort,
        invite_repo: InviteRepoPort,
        session_repo: SessionRepoPort,
    ) -> None:
        self.user_repo = user_repo
        self.invite_repo = invite_repo
        self.session_repo = session_repo

    def register(
        self,
        username: str,
        display_name: str,
        password: str,
        invite_code: str,
        user_agent: str,
        ip: str,
    ) -> AuthTokens:
        """Регистрирует пользователя по валидному инвайту."""

        prepared_username = username.strip()
        if len(prepared_username) < 3:
            raise ValidationError("Слишком короткий логин")

        if self.user_repo.get_by_username(prepared_username) is not None:
            raise ValidationError("Логин уже занят")

        invite = self.invite_repo.get_by_code(invite_code.strip())
        now = datetime.now(tz=UTC)
        if invite is None or not invite.is_active:
            raise ValidationError("Инвайт недействителен")
        invite_expires_at = invite.expires_at
        if invite_expires_at.tzinfo is None:
            invite_expires_at = invite_expires_at.replace(tzinfo=UTC)
        if invite_expires_at < now:
            raise ValidationError("Инвайт истёк")
        if invite.used_count >= invite.max_uses:
            raise ValidationError("Инвайт исчерпан")

        password_hash = hash_password(password)
        user = self.user_repo.create(
            username=prepared_username,
            display_name=display_name.strip() or prepared_username,
            password_hash=password_hash,
        )
        self.invite_repo.consume(invite)
        return self._issue_tokens(user.id, user_agent=user_agent, ip=ip)

    def login(self, username: str, password: str, user_agent: str, ip: str) -> AuthTokens:
        """Выполняет вход по логину и паролю."""

        user = self.user_repo.get_by_username(username.strip())
        if user is None or not user.is_active:
            raise AuthError("Неверный логин или пароль")

        if not verify_password(password, user.password_hash):
            raise AuthError("Неверный логин или пароль")

        return self._issue_tokens(user.id, user_agent=user_agent, ip=ip)

    def refresh(self, refresh_token: str, user_agent: str, ip: str) -> AuthTokens:
        """Обновляет access token и ротацирует refresh token."""

        payload = decode_token(refresh_token, expected_scope="refresh")
        user_id = int(payload["sub"])
        session_id = int(payload["sid"])

        saved_session = self.session_repo.get_by_refresh_hash(hash_refresh_token(refresh_token))
        if saved_session is None or saved_session.id != session_id:
            raise AuthError("Сессия недействительна")

        tokens = self._build_tokens(user_id=user_id, session_id=session_id)
        self.session_repo.set_refresh_hash(session_id=session_id, refresh_token_hash=hash_refresh_token(tokens.refresh_token))
        return tokens

    def logout(self, refresh_token: str) -> None:
        """Завершает текущую сессию по refresh token."""

        session = self.session_repo.get_by_refresh_hash(hash_refresh_token(refresh_token))
        if session is None:
            return
        self.session_repo.revoke(session.id)

    def logout_all(self, user_id: int) -> None:
        """Завершает все сессии пользователя."""

        self.session_repo.revoke_all(user_id)

    def create_invite(
        self,
        code: str,
        created_by: int,
        ttl_hours: int,
        max_uses: int,
    ):
        """Создаёт новый инвайт."""

        prepared_code = code.strip()
        if len(prepared_code) < 6:
            raise ValidationError("Код инвайта слишком короткий")
        if self.invite_repo.get_by_code(prepared_code) is not None:
            raise ValidationError("Инвайт с таким кодом уже существует")

        expires_at = datetime.now(tz=UTC) + timedelta(hours=ttl_hours)
        return self.invite_repo.create(
            code=prepared_code,
            created_by=created_by,
            expires_at=expires_at,
            max_uses=max_uses,
        )

    def ensure_bootstrap_invite(self, code: str, ttl_hours: int, max_uses: int) -> None:
        """Создаёт стартовый инвайт при первом запуске."""

        existing = self.invite_repo.get_by_code(code)
        if existing is not None:
            return

        self.invite_repo.create(
            code=code,
            created_by=None,
            expires_at=datetime.now(tz=UTC) + timedelta(hours=ttl_hours),
            max_uses=max_uses,
        )

    def _issue_tokens(self, user_id: int, user_agent: str, ip: str) -> AuthTokens:
        session = self.session_repo.create(
            user_id=user_id,
            refresh_token_hash="bootstrap",
            user_agent=user_agent,
            ip=ip,
        )
        tokens = self._build_tokens(user_id=user_id, session_id=session.id)
        self.session_repo.set_refresh_hash(session.id, hash_refresh_token(tokens.refresh_token))
        return tokens

    @staticmethod
    def _build_tokens(user_id: int, session_id: int) -> AuthTokens:
        access_token = build_access_token(user_id=user_id)
        refresh_token = build_refresh_token(user_id=user_id, session_id=session_id)
        return AuthTokens(access_token=access_token, refresh_token=refresh_token, user_id=user_id)
