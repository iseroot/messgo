from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from app.application.errors import NotFoundError, PermissionDeniedError, ValidationError
from app.application.services.message_service import MessageService


@dataclass
class FakeMember:
    user_id: int


@dataclass
class FakeMessage:
    id: int
    chat_id: int
    sender_id: int
    text: str
    status: str
    created_at: datetime = datetime.now(tz=UTC)


class FakeChatRepo:
    def __init__(self):
        self.members = {1: [FakeMember(1), FakeMember(2)]}
        self.last_read = None

    def is_member(self, chat_id: int, user_id: int) -> bool:
        return any(member.user_id == user_id for member in self.members.get(chat_id, []))

    def list_members(self, chat_id: int):
        return self.members.get(chat_id, [])

    def set_last_read_message(self, chat_id: int, user_id: int, message_id: int):
        self.last_read = (chat_id, user_id, message_id)


class FakeMessageRepo:
    def __init__(self):
        self.messages: dict[int, FakeMessage] = {}
        self._id = 1

    def create_message(self, chat_id: int, sender_id: int, message_type: str, text: str, status: str, reply_to_message_id=None):
        message = FakeMessage(id=self._id, chat_id=chat_id, sender_id=sender_id, text=text, status=status)
        self.messages[self._id] = message
        self._id += 1
        return message

    def list_messages(self, chat_id: int, limit: int, offset: int):
        return list(self.messages.values())[offset : offset + limit]

    def get_message(self, message_id: int):
        return self.messages.get(message_id)

    def update_status(self, message_id: int, status: str):
        message = self.messages.get(message_id)
        if message is None:
            return None
        message.status = status
        return message


@pytest.fixture
def service():
    return MessageService(chat_repo=FakeChatRepo(), message_repo=FakeMessageRepo())


def test_send_message_sets_delivered_when_recipient_online(service: MessageService):
    result = service.send_text_message(chat_id=1, sender_id=1, text="Привет", online_user_ids={2})
    assert result.status == "delivered"


def test_send_message_rejects_empty(service: MessageService):
    with pytest.raises(ValidationError):
        service.send_text_message(chat_id=1, sender_id=1, text=" ", online_user_ids={2})


def test_send_message_rejects_non_member(service: MessageService):
    with pytest.raises(PermissionDeniedError):
        service.send_text_message(chat_id=1, sender_id=999, text="x", online_user_ids=set())


def test_list_messages_checks_membership(service: MessageService):
    with pytest.raises(PermissionDeniedError):
        service.list_messages(chat_id=1, user_id=999, limit=10, offset=0)


def test_mark_read_updates_status(service: MessageService):
    result = service.send_text_message(chat_id=1, sender_id=1, text="Сообщение", online_user_ids=set())
    updated = service.mark_read(message_id=result.message_id, user_id=2)
    assert updated is not None
    assert updated.status == "read"


def test_mark_read_fails_if_message_missing(service: MessageService):
    with pytest.raises(NotFoundError):
        service.mark_read(message_id=500, user_id=1)
