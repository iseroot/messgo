from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import Session

from app.infrastructure.models import (
    CallORM,
    CallSignalEventORM,
    ChatMemberORM,
    ChatORM,
    DeviceSessionORM,
    InviteORM,
    MessageORM,
    UserORM,
)


class UserRepository:
    """SQLAlchemy-репозиторий пользователей."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_username(self, username: str) -> UserORM | None:
        stmt = select(UserORM).where(func.lower(UserORM.username) == username.lower())
        return self.db.scalar(stmt)

    def get_by_id(self, user_id: int) -> UserORM | None:
        return self.db.get(UserORM, user_id)

    def create(self, username: str, display_name: str, password_hash: str) -> UserORM:
        user = UserORM(username=username, display_name=display_name, password_hash=password_hash)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_last_seen(self, user_id: int, seen_at: datetime) -> None:
        user = self.db.get(UserORM, user_id)
        if user is None:
            return
        user.last_seen_at = seen_at
        self.db.add(user)
        self.db.commit()


class InviteRepository:
    """SQLAlchemy-репозиторий инвайтов."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_code(self, code: str) -> InviteORM | None:
        stmt = select(InviteORM).where(InviteORM.code == code)
        return self.db.scalar(stmt)

    def consume(self, invite: InviteORM) -> InviteORM:
        invite.used_count += 1
        if invite.used_count >= invite.max_uses:
            invite.is_active = False
        self.db.add(invite)
        self.db.commit()
        self.db.refresh(invite)
        return invite

    def create(
        self,
        code: str,
        created_by: int | None,
        expires_at: datetime,
        max_uses: int,
    ) -> InviteORM:
        invite = InviteORM(
            code=code,
            created_by=created_by,
            expires_at=expires_at,
            max_uses=max_uses,
            used_count=0,
            is_active=True,
        )
        self.db.add(invite)
        self.db.commit()
        self.db.refresh(invite)
        return invite


class SessionRepository:
    """SQLAlchemy-репозиторий сессий устройств."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, user_id: int, refresh_token_hash: str, user_agent: str, ip: str) -> DeviceSessionORM:
        session = DeviceSessionORM(
            user_id=user_id,
            refresh_token_hash=refresh_token_hash,
            user_agent=user_agent,
            ip=ip,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_by_refresh_hash(self, refresh_token_hash: str) -> DeviceSessionORM | None:
        stmt = select(DeviceSessionORM).where(
            and_(
                DeviceSessionORM.refresh_token_hash == refresh_token_hash,
                DeviceSessionORM.is_revoked.is_(False),
            )
        )
        return self.db.scalar(stmt)

    def revoke(self, session_id: int) -> None:
        session = self.db.get(DeviceSessionORM, session_id)
        if session is None:
            return
        session.is_revoked = True
        session.last_active_at = datetime.now(tz=UTC)
        self.db.add(session)
        self.db.commit()

    def revoke_all(self, user_id: int) -> None:
        stmt = select(DeviceSessionORM).where(
            and_(DeviceSessionORM.user_id == user_id, DeviceSessionORM.is_revoked.is_(False))
        )
        sessions = self.db.scalars(stmt).all()
        for session in sessions:
            session.is_revoked = True
            session.last_active_at = datetime.now(tz=UTC)
            self.db.add(session)
        self.db.commit()

    def set_refresh_hash(self, session_id: int, refresh_token_hash: str) -> DeviceSessionORM | None:
        session = self.db.get(DeviceSessionORM, session_id)
        if session is None:
            return None
        session.refresh_token_hash = refresh_token_hash
        session.last_active_at = datetime.now(tz=UTC)
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session


class ChatRepository:
    """SQLAlchemy-репозиторий чатов."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def find_direct_chat(self, first_user_id: int, second_user_id: int) -> ChatORM | None:
        stmt = (
            select(ChatORM)
            .join(ChatMemberORM, ChatMemberORM.chat_id == ChatORM.id)
            .where(ChatORM.type == "direct")
            .where(ChatMemberORM.user_id.in_([first_user_id, second_user_id]))
            .group_by(ChatORM.id)
            .having(func.count(ChatMemberORM.user_id) == 2)
        )
        return self.db.scalar(stmt)

    def create_chat(self, chat_type: str, title: str | None, created_by: int) -> ChatORM:
        chat = ChatORM(type=chat_type, title=title, created_by=created_by)
        self.db.add(chat)
        self.db.commit()
        self.db.refresh(chat)
        return chat

    def add_member(self, chat_id: int, user_id: int, role: str = "member") -> ChatMemberORM:
        exists_stmt = select(ChatMemberORM).where(
            and_(ChatMemberORM.chat_id == chat_id, ChatMemberORM.user_id == user_id)
        )
        existing = self.db.scalar(exists_stmt)
        if existing is not None:
            return existing

        member = ChatMemberORM(chat_id=chat_id, user_id=user_id, role=role)
        self.db.add(member)
        self.db.commit()
        self.db.refresh(member)
        return member

    def list_user_chats(self, user_id: int) -> list[ChatORM]:
        stmt = (
            select(ChatORM)
            .join(ChatMemberORM, ChatMemberORM.chat_id == ChatORM.id)
            .where(ChatMemberORM.user_id == user_id)
            .order_by(desc(ChatORM.created_at))
        )
        return list(self.db.scalars(stmt).all())

    def is_member(self, chat_id: int, user_id: int) -> bool:
        stmt = select(ChatMemberORM.id).where(
            and_(ChatMemberORM.chat_id == chat_id, ChatMemberORM.user_id == user_id)
        )
        return self.db.scalar(stmt) is not None

    def list_members(self, chat_id: int) -> list[ChatMemberORM]:
        stmt = select(ChatMemberORM).where(ChatMemberORM.chat_id == chat_id)
        return list(self.db.scalars(stmt).all())

    def set_last_read_message(self, chat_id: int, user_id: int, message_id: int) -> None:
        stmt = select(ChatMemberORM).where(
            and_(ChatMemberORM.chat_id == chat_id, ChatMemberORM.user_id == user_id)
        )
        member = self.db.scalar(stmt)
        if member is None:
            return
        member.last_read_message_id = message_id
        self.db.add(member)
        self.db.commit()


class MessageRepository:
    """SQLAlchemy-репозиторий сообщений."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_message(
        self,
        chat_id: int,
        sender_id: int,
        message_type: str,
        text: str,
        status: str,
        reply_to_message_id: int | None = None,
    ) -> MessageORM:
        message = MessageORM(
            chat_id=chat_id,
            sender_id=sender_id,
            type=message_type,
            text=text,
            status=status,
            reply_to_message_id=reply_to_message_id,
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def list_messages(self, chat_id: int, limit: int, offset: int) -> list[MessageORM]:
        stmt = (
            select(MessageORM)
            .where(MessageORM.chat_id == chat_id)
            .order_by(desc(MessageORM.created_at))
            .limit(limit)
            .offset(offset)
        )
        data = self.db.scalars(stmt).all()
        return list(reversed(list(data)))

    def get_message(self, message_id: int) -> MessageORM | None:
        return self.db.get(MessageORM, message_id)

    def update_status(self, message_id: int, status: str) -> MessageORM | None:
        message = self.db.get(MessageORM, message_id)
        if message is None:
            return None
        message.status = status
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message


class CallRepository:
    """SQLAlchemy-репозиторий звонков."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_call(self, chat_id: int, initiator_id: int, status: str) -> CallORM:
        call = CallORM(chat_id=chat_id, initiator_id=initiator_id, status=status)
        self.db.add(call)
        self.db.commit()
        self.db.refresh(call)
        return call

    def get_call(self, call_id: int) -> CallORM | None:
        return self.db.get(CallORM, call_id)

    def update_status(self, call_id: int, status: str, ended_at: datetime | None = None) -> CallORM | None:
        call = self.db.get(CallORM, call_id)
        if call is None:
            return None
        call.status = status
        call.ended_at = ended_at
        self.db.add(call)
        self.db.commit()
        self.db.refresh(call)
        return call

    def add_signal_event(
        self,
        call_id: int,
        from_user_id: int,
        to_user_id: int,
        event_type: str,
        payload: str,
    ) -> None:
        event = CallSignalEventORM(
            call_id=call_id,
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            type=event_type,
            payload=payload,
        )
        self.db.add(event)
        self.db.commit()
