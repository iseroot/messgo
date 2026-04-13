from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from app.application.errors import AuthError, ValidationError
from app.application.services.auth_service import AuthService
from app.core.config import get_settings
from app.core.security import hash_refresh_token


@dataclass
class FakeUser:
    id: int
    username: str
    display_name: str
    password_hash: str
    is_active: bool = True


@dataclass
class FakeInvite:
    code: str
    expires_at: datetime
    max_uses: int
    used_count: int = 0
    is_active: bool = True


@dataclass
class FakeSession:
    id: int
    user_id: int
    refresh_token_hash: str
    is_revoked: bool = False


class FakeUserRepo:
    def __init__(self):
        self.users: dict[int, FakeUser] = {}
        self._id = 1

    def get_by_username(self, username: str):
        for user in self.users.values():
            if user.username.lower() == username.lower():
                return user
        return None

    def get_by_id(self, user_id: int):
        return self.users.get(user_id)

    def create(self, username: str, display_name: str, password_hash: str):
        user = FakeUser(id=self._id, username=username, display_name=display_name, password_hash=password_hash)
        self.users[self._id] = user
        self._id += 1
        return user

    def update_last_seen(self, user_id: int, seen_at: datetime):
        return None


class FakeInviteRepo:
    def __init__(self):
        self.invites: dict[str, FakeInvite] = {}

    def get_by_code(self, code: str):
        return self.invites.get(code)

    def consume(self, invite):
        invite.used_count += 1
        if invite.used_count >= invite.max_uses:
            invite.is_active = False
        return invite

    def create(self, code: str, created_by: int | None, expires_at: datetime, max_uses: int):
        invite = FakeInvite(code=code, expires_at=expires_at, max_uses=max_uses)
        self.invites[code] = invite
        return invite


class FakeSessionRepo:
    def __init__(self):
        self.sessions: dict[int, FakeSession] = {}
        self._id = 1

    def create(self, user_id: int, refresh_token_hash: str, user_agent: str, ip: str):
        session = FakeSession(id=self._id, user_id=user_id, refresh_token_hash=refresh_token_hash)
        self.sessions[self._id] = session
        self._id += 1
        return session

    def get_by_refresh_hash(self, refresh_token_hash: str):
        for session in self.sessions.values():
            if session.refresh_token_hash == refresh_token_hash and not session.is_revoked:
                return session
        return None

    def revoke(self, session_id: int):
        session = self.sessions.get(session_id)
        if session:
            session.is_revoked = True

    def revoke_all(self, user_id: int):
        for session in self.sessions.values():
            if session.user_id == user_id:
                session.is_revoked = True

    def set_refresh_hash(self, session_id: int, refresh_token_hash: str):
        session = self.sessions.get(session_id)
        if session:
            session.refresh_token_hash = refresh_token_hash
        return session


@pytest.fixture
def service(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "unit-secret-123456789012345678901234567890")
    get_settings.cache_clear()

    user_repo = FakeUserRepo()
    invite_repo = FakeInviteRepo()
    session_repo = FakeSessionRepo()
    invite_repo.create(
        code="INVITE-1",
        created_by=None,
        expires_at=datetime.now(tz=UTC) + timedelta(hours=2),
        max_uses=2,
    )
    return AuthService(user_repo=user_repo, invite_repo=invite_repo, session_repo=session_repo)


def test_register_success(service: AuthService):
    tokens = service.register(
        username="alice",
        display_name="Alice",
        password="very-strong-password",
        invite_code="INVITE-1",
        user_agent="pytest",
        ip="127.0.0.1",
    )
    assert tokens.user_id == 1
    assert tokens.access_token
    assert tokens.refresh_token


def test_register_fails_on_missing_invite(service: AuthService):
    with pytest.raises(ValidationError):
        service.register(
            username="alice",
            display_name="Alice",
            password="very-strong-password",
            invite_code="UNKNOWN",
            user_agent="pytest",
            ip="127.0.0.1",
        )


def test_register_fails_on_short_username(service: AuthService):
    with pytest.raises(ValidationError):
        service.register(
            username="ab",
            display_name="Alice",
            password="very-strong-password",
            invite_code="INVITE-1",
            user_agent="pytest",
            ip="127.0.0.1",
        )


def test_register_fails_on_duplicate_username(service: AuthService):
    service.register(
        username="alice",
        display_name="Alice",
        password="very-strong-password",
        invite_code="INVITE-1",
        user_agent="pytest",
        ip="127.0.0.1",
    )
    with pytest.raises(ValidationError):
        service.register(
            username="alice",
            display_name="Alice",
            password="very-strong-password",
            invite_code="INVITE-1",
            user_agent="pytest",
            ip="127.0.0.1",
        )


def test_register_fails_on_expired_invite(service: AuthService):
    service.invite_repo.create(
        code="EXPIRED-1",
        created_by=None,
        expires_at=datetime.now(tz=UTC) - timedelta(minutes=1),
        max_uses=1,
    )
    with pytest.raises(ValidationError):
        service.register(
            username="alice",
            display_name="Alice",
            password="very-strong-password",
            invite_code="EXPIRED-1",
            user_agent="pytest",
            ip="127.0.0.1",
        )


def test_register_fails_on_exhausted_invite(service: AuthService):
    invite = service.invite_repo.create(
        code="LIMITED-1",
        created_by=None,
        expires_at=datetime.now(tz=UTC) + timedelta(minutes=10),
        max_uses=1,
    )
    invite.used_count = 1
    with pytest.raises(ValidationError):
        service.register(
            username="alice",
            display_name="Alice",
            password="very-strong-password",
            invite_code="LIMITED-1",
            user_agent="pytest",
            ip="127.0.0.1",
        )


def test_login_and_refresh(service: AuthService):
    service.register(
        username="alice",
        display_name="Alice",
        password="very-strong-password",
        invite_code="INVITE-1",
        user_agent="pytest",
        ip="127.0.0.1",
    )

    login_tokens = service.login(
        username="alice",
        password="very-strong-password",
        user_agent="pytest",
        ip="127.0.0.1",
    )
    refreshed = service.refresh(
        refresh_token=login_tokens.refresh_token,
        user_agent="pytest",
        ip="127.0.0.1",
    )

    assert refreshed.user_id == login_tokens.user_id
    assert hash_refresh_token(login_tokens.refresh_token) != hash_refresh_token(refreshed.refresh_token)


def test_login_fails_with_wrong_password(service: AuthService):
    service.register(
        username="alice",
        display_name="Alice",
        password="very-strong-password",
        invite_code="INVITE-1",
        user_agent="pytest",
        ip="127.0.0.1",
    )

    with pytest.raises(AuthError):
        service.login(
            username="alice",
            password="wrong-password",
            user_agent="pytest",
            ip="127.0.0.1",
        )


def test_login_fails_for_inactive_user(service: AuthService):
    service.register(
        username="alice",
        display_name="Alice",
        password="very-strong-password",
        invite_code="INVITE-1",
        user_agent="pytest",
        ip="127.0.0.1",
    )
    user = service.user_repo.get_by_username("alice")
    user.is_active = False

    with pytest.raises(AuthError):
        service.login(
            username="alice",
            password="very-strong-password",
            user_agent="pytest",
            ip="127.0.0.1",
        )


def test_logout_all_revokes_sessions(service: AuthService):
    first = service.register(
        username="alice",
        display_name="Alice",
        password="very-strong-password",
        invite_code="INVITE-1",
        user_agent="pytest",
        ip="127.0.0.1",
    )
    service.refresh(refresh_token=first.refresh_token, user_agent="pytest", ip="127.0.0.1")
    service.logout_all(user_id=1)

    with pytest.raises(AuthError):
        service.refresh(refresh_token=first.refresh_token, user_agent="pytest", ip="127.0.0.1")


def test_create_invite(service: AuthService):
    invite = service.create_invite(code="INVITE-2", created_by=1, ttl_hours=12, max_uses=3)
    assert invite.code == "INVITE-2"
    assert invite.max_uses == 3


def test_create_invite_validations(service: AuthService):
    with pytest.raises(ValidationError):
        service.create_invite(code="short", created_by=1, ttl_hours=12, max_uses=1)

    service.create_invite(code="INVITE-DUP", created_by=1, ttl_hours=12, max_uses=1)
    with pytest.raises(ValidationError):
        service.create_invite(code="INVITE-DUP", created_by=1, ttl_hours=12, max_uses=1)


def test_logout_missing_session_is_noop(service: AuthService):
    service.logout("missing-token")


def test_bootstrap_invite_creates_only_once(service: AuthService):
    service.ensure_bootstrap_invite(code="BOOTSTRAP-ONE", ttl_hours=1, max_uses=1)
    service.ensure_bootstrap_invite(code="BOOTSTRAP-ONE", ttl_hours=1, max_uses=1)
    invite = service.invite_repo.get_by_code("BOOTSTRAP-ONE")
    assert invite is not None
