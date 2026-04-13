from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.infrastructure.models import (
    CallORM,
    ChatMemberORM,
    ChatORM,
    DeviceSessionORM,
    InviteORM,
    MessageORM,
    UserORM,
)


class UserRepoPort(Protocol):
    """Контракт репозитория пользователей."""

    def get_by_username(self, username: str) -> UserORM | None: ...

    def get_by_id(self, user_id: int) -> UserORM | None: ...

    def create(self, username: str, display_name: str, password_hash: str) -> UserORM: ...

    def update_last_seen(self, user_id: int, seen_at: datetime) -> None: ...


class InviteRepoPort(Protocol):
    """Контракт репозитория инвайтов."""

    def get_by_code(self, code: str) -> InviteORM | None: ...

    def consume(self, invite: InviteORM) -> InviteORM: ...

    def create(
        self,
        code: str,
        created_by: int | None,
        expires_at: datetime,
        max_uses: int,
    ) -> InviteORM: ...


class SessionRepoPort(Protocol):
    """Контракт репозитория сессий устройств."""

    def create(self, user_id: int, refresh_token_hash: str, user_agent: str, ip: str) -> DeviceSessionORM: ...

    def get_by_refresh_hash(self, refresh_token_hash: str) -> DeviceSessionORM | None: ...

    def revoke(self, session_id: int) -> None: ...

    def revoke_all(self, user_id: int) -> None: ...

    def set_refresh_hash(self, session_id: int, refresh_token_hash: str) -> DeviceSessionORM | None: ...


class ChatRepoPort(Protocol):
    """Контракт репозитория чатов."""

    def find_direct_chat(self, first_user_id: int, second_user_id: int) -> ChatORM | None: ...

    def create_chat(self, chat_type: str, title: str | None, created_by: int) -> ChatORM: ...

    def add_member(self, chat_id: int, user_id: int, role: str = "member") -> ChatMemberORM: ...

    def list_user_chats(self, user_id: int) -> list[ChatORM]: ...

    def is_member(self, chat_id: int, user_id: int) -> bool: ...

    def list_members(self, chat_id: int) -> list[ChatMemberORM]: ...

    def set_last_read_message(self, chat_id: int, user_id: int, message_id: int) -> None: ...


class MessageRepoPort(Protocol):
    """Контракт репозитория сообщений."""

    def create_message(
        self,
        chat_id: int,
        sender_id: int,
        message_type: str,
        text: str,
        status: str,
        reply_to_message_id: int | None = None,
    ) -> MessageORM: ...

    def list_messages(self, chat_id: int, limit: int, offset: int) -> list[MessageORM]: ...

    def get_message(self, message_id: int) -> MessageORM | None: ...

    def update_status(self, message_id: int, status: str) -> MessageORM | None: ...


class CallRepoPort(Protocol):
    """Контракт репозитория звонков."""

    def create_call(self, chat_id: int, initiator_id: int, status: str) -> CallORM: ...

    def get_call(self, call_id: int) -> CallORM | None: ...

    def update_status(self, call_id: int, status: str, ended_at: datetime | None = None) -> CallORM | None: ...

    def add_signal_event(
        self,
        call_id: int,
        from_user_id: int,
        to_user_id: int,
        event_type: str,
        payload: str,
    ) -> None: ...
