from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from app.application.errors import NotFoundError, ValidationError
from app.application.services.chat_service import ChatService
from app.core.config import get_settings


@dataclass
class FakeUser:
    id: int
    is_active: bool = True


@dataclass
class FakeChat:
    id: int
    type: str
    title: str | None
    created_by: int
    created_at: datetime = datetime.now(tz=UTC)


@dataclass
class FakeMember:
    chat_id: int
    user_id: int
    role: str


class FakeUserRepo:
    def __init__(self):
        self.users = {1: FakeUser(1), 2: FakeUser(2), 3: FakeUser(3)}

    def get_by_id(self, user_id: int):
        return self.users.get(user_id)


class FakeChatRepo:
    def __init__(self):
        self.chats: dict[int, FakeChat] = {}
        self.members: list[FakeMember] = []
        self._id = 1

    def find_direct_chat(self, first_user_id: int, second_user_id: int):
        for chat in self.chats.values():
            if chat.type != "direct":
                continue
            member_ids = {m.user_id for m in self.members if m.chat_id == chat.id}
            if member_ids == {first_user_id, second_user_id}:
                return chat
        return None

    def create_chat(self, chat_type: str, title: str | None, created_by: int):
        chat = FakeChat(id=self._id, type=chat_type, title=title, created_by=created_by)
        self.chats[self._id] = chat
        self._id += 1
        return chat

    def add_member(self, chat_id: int, user_id: int, role: str = "member"):
        member = FakeMember(chat_id=chat_id, user_id=user_id, role=role)
        self.members.append(member)
        return member

    def list_user_chats(self, user_id: int):
        chat_ids = {m.chat_id for m in self.members if m.user_id == user_id}
        return [chat for chat in self.chats.values() if chat.id in chat_ids]


@pytest.fixture
def service(monkeypatch):
    monkeypatch.setenv("MAX_GROUP_SIZE", "10")
    get_settings.cache_clear()
    return ChatService(chat_repo=FakeChatRepo(), user_repo=FakeUserRepo())


def test_create_direct_chat(service: ChatService):
    chat = service.create_direct_chat(owner_id=1, peer_id=2)
    assert chat.type == "direct"


def test_create_direct_chat_with_same_user_fails(service: ChatService):
    with pytest.raises(ValidationError):
        service.create_direct_chat(owner_id=1, peer_id=1)


def test_create_direct_chat_with_missing_peer_fails(service: ChatService):
    with pytest.raises(NotFoundError):
        service.create_direct_chat(owner_id=1, peer_id=99)


def test_create_group_chat(service: ChatService):
    chat = service.create_group_chat(owner_id=1, title="Команда", member_ids=[2, 3])
    assert chat.type == "group"
    assert chat.title == "Команда"


def test_create_group_chat_with_short_title_fails(service: ChatService):
    with pytest.raises(ValidationError):
        service.create_group_chat(owner_id=1, title="a", member_ids=[2])
