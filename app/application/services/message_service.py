from __future__ import annotations

from dataclasses import dataclass
from html import escape

from app.application.errors import NotFoundError, PermissionDeniedError, ValidationError
from app.application.ports import ChatRepoPort, MessageRepoPort
from app.core.config import get_settings
from app.domain.enums import MessageStatus, MessageType


@dataclass(slots=True)
class SendMessageResult:
    """Результат отправки сообщения."""

    message_id: int
    chat_id: int
    sender_id: int
    text: str
    status: str
    member_ids: list[int]


class MessageService:
    """Сервис сценариев отправки и чтения сообщений."""

    def __init__(self, chat_repo: ChatRepoPort, message_repo: MessageRepoPort) -> None:
        self.chat_repo = chat_repo
        self.message_repo = message_repo
        self.settings = get_settings()

    def send_text_message(
        self,
        chat_id: int,
        sender_id: int,
        text: str,
        online_user_ids: set[int],
        reply_to_message_id: int | None = None,
    ) -> SendMessageResult:
        """Проверяет права и создаёт текстовое сообщение."""

        if not self.chat_repo.is_member(chat_id, sender_id):
            raise PermissionDeniedError("Нет доступа к чату")

        prepared_text = text.strip()
        if not prepared_text:
            raise ValidationError("Пустое сообщение")
        if len(prepared_text) > self.settings.max_message_length:
            raise ValidationError("Сообщение слишком длинное")

        member_ids = [member.user_id for member in self.chat_repo.list_members(chat_id)]
        recipient_ids = [user_id for user_id in member_ids if user_id != sender_id]
        status = MessageStatus.SENT.value
        if any(user_id in online_user_ids for user_id in recipient_ids):
            status = MessageStatus.DELIVERED.value

        safe_text = escape(prepared_text)
        message = self.message_repo.create_message(
            chat_id=chat_id,
            sender_id=sender_id,
            message_type=MessageType.TEXT.value,
            text=safe_text,
            status=status,
            reply_to_message_id=reply_to_message_id,
        )
        return SendMessageResult(
            message_id=message.id,
            chat_id=message.chat_id,
            sender_id=message.sender_id,
            text=message.text,
            status=message.status,
            member_ids=member_ids,
        )

    def list_messages(self, chat_id: int, user_id: int, limit: int, offset: int):
        """Возвращает историю сообщений порциями."""

        if not self.chat_repo.is_member(chat_id, user_id):
            raise PermissionDeniedError("Нет доступа к чату")

        return self.message_repo.list_messages(chat_id=chat_id, limit=limit, offset=offset)

    def mark_read(self, message_id: int, user_id: int):
        """Отмечает сообщение как прочитанное для участника чата."""

        message = self.message_repo.get_message(message_id)
        if message is None:
            raise NotFoundError("Сообщение не найдено")

        if not self.chat_repo.is_member(message.chat_id, user_id):
            raise PermissionDeniedError("Нет доступа к чату")

        self.chat_repo.set_last_read_message(message.chat_id, user_id, message.id)
        return self.message_repo.update_status(message_id, MessageStatus.READ.value)
