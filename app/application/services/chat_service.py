from __future__ import annotations

from dataclasses import dataclass

from app.application.errors import NotFoundError, ValidationError
from app.application.ports import ChatRepoPort, UserRepoPort
from app.core.config import get_settings
from app.domain.enums import ChatType


@dataclass(slots=True)
class ChatView:
    """Представление чата для API."""

    id: int
    type: str
    title: str | None


class ChatService:
    """Сервис сценариев работы с чатами."""

    def __init__(self, chat_repo: ChatRepoPort, user_repo: UserRepoPort) -> None:
        self.chat_repo = chat_repo
        self.user_repo = user_repo
        self.settings = get_settings()

    def create_direct_chat(self, owner_id: int, peer_id: int):
        """Создаёт или возвращает прямой чат 1:1."""

        if owner_id == peer_id:
            raise ValidationError("Нельзя создать direct чат с самим собой")

        peer = self.user_repo.get_by_id(peer_id)
        if peer is None or not peer.is_active:
            raise NotFoundError("Собеседник не найден")

        existing = self.chat_repo.find_direct_chat(owner_id, peer_id)
        if existing is not None:
            return existing

        chat = self.chat_repo.create_chat(chat_type=ChatType.DIRECT.value, title=None, created_by=owner_id)
        self.chat_repo.add_member(chat.id, owner_id, role="owner")
        self.chat_repo.add_member(chat.id, peer_id, role="member")
        return chat

    def create_group_chat(self, owner_id: int, title: str, member_ids: list[int]):
        """Создаёт групповой чат с ограничением размера."""

        clean_title = title.strip()
        if len(clean_title) < 2:
            raise ValidationError("Слишком короткое название группы")

        unique_members = sorted({owner_id, *member_ids})
        if len(unique_members) > self.settings.max_group_size:
            raise ValidationError("Слишком много участников для MVP")

        for user_id in unique_members:
            user = self.user_repo.get_by_id(user_id)
            if user is None or not user.is_active:
                raise NotFoundError(f"Пользователь {user_id} не найден")

        chat = self.chat_repo.create_chat(
            chat_type=ChatType.GROUP.value,
            title=clean_title,
            created_by=owner_id,
        )
        for member_id in unique_members:
            role = "owner" if member_id == owner_id else "member"
            self.chat_repo.add_member(chat.id, member_id, role=role)
        return chat

    def list_user_chats(self, user_id: int):
        """Возвращает список чатов пользователя."""

        return self.chat_repo.list_user_chats(user_id)
