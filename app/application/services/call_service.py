from __future__ import annotations

from datetime import UTC, datetime

from app.application.errors import NotFoundError, PermissionDeniedError, ValidationError
from app.application.ports import CallRepoPort, ChatRepoPort
from app.domain.enums import CallStatus


class CallService:
    """Сервис сценариев аудиозвонков 1:1."""

    def __init__(self, chat_repo: ChatRepoPort, call_repo: CallRepoPort) -> None:
        self.chat_repo = chat_repo
        self.call_repo = call_repo

    def start_call(self, chat_id: int, initiator_id: int, to_user_id: int):
        """Создаёт звонок и возвращает его id."""

        if not self.chat_repo.is_member(chat_id, initiator_id):
            raise PermissionDeniedError("Нет доступа к чату")
        if not self.chat_repo.is_member(chat_id, to_user_id):
            raise ValidationError("Получатель не состоит в чате")
        if initiator_id == to_user_id:
            raise ValidationError("Нельзя звонить самому себе")

        call = self.call_repo.create_call(
            chat_id=chat_id,
            initiator_id=initiator_id,
            status=CallStatus.RINGING.value,
        )
        return call

    def add_signal(self, call_id: int, from_user_id: int, to_user_id: int, event_type: str, payload: str) -> None:
        """Сохраняет событие сигналинга WebRTC."""

        call = self.call_repo.get_call(call_id)
        if call is None:
            raise NotFoundError("Звонок не найден")
        if not self.chat_repo.is_member(call.chat_id, from_user_id):
            raise PermissionDeniedError("Нет доступа к звонку")
        if not self.chat_repo.is_member(call.chat_id, to_user_id):
            raise ValidationError("Получатель не состоит в чате")

        self.call_repo.add_signal_event(
            call_id=call_id,
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            event_type=event_type,
            payload=payload,
        )

    def set_status(self, call_id: int, user_id: int, status: str):
        """Обновляет статус звонка с проверкой прав."""

        call = self.call_repo.get_call(call_id)
        if call is None:
            raise NotFoundError("Звонок не найден")
        if not self.chat_repo.is_member(call.chat_id, user_id):
            raise PermissionDeniedError("Нет доступа к звонку")

        ended_at = datetime.now(tz=UTC) if status in {CallStatus.ENDED.value, CallStatus.DECLINED.value} else None
        updated = self.call_repo.update_status(call_id=call_id, status=status, ended_at=ended_at)
        if updated is None:
            raise NotFoundError("Звонок не найден")
        return updated
