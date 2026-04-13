from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.application.errors import NotFoundError, PermissionDeniedError, ValidationError
from app.application.services.call_service import CallService


@dataclass
class FakeCall:
    id: int
    chat_id: int
    initiator_id: int
    status: str
    ended_at: object = None


class FakeChatRepo:
    def __init__(self):
        self.members = {1: {1, 2}}

    def is_member(self, chat_id: int, user_id: int) -> bool:
        return user_id in self.members.get(chat_id, set())


class FakeCallRepo:
    def __init__(self):
        self.calls: dict[int, FakeCall] = {}
        self._id = 1
        self.events = []

    def create_call(self, chat_id: int, initiator_id: int, status: str):
        call = FakeCall(id=self._id, chat_id=chat_id, initiator_id=initiator_id, status=status)
        self.calls[self._id] = call
        self._id += 1
        return call

    def get_call(self, call_id: int):
        return self.calls.get(call_id)

    def update_status(self, call_id: int, status: str, ended_at=None):
        call = self.calls.get(call_id)
        if call is None:
            return None
        call.status = status
        call.ended_at = ended_at
        return call

    def add_signal_event(self, call_id: int, from_user_id: int, to_user_id: int, event_type: str, payload: str):
        self.events.append((call_id, from_user_id, to_user_id, event_type, payload))


class FakeCallRepoNoUpdate(FakeCallRepo):
    def update_status(self, call_id: int, status: str, ended_at=None):
        return None


@pytest.fixture
def service():
    return CallService(chat_repo=FakeChatRepo(), call_repo=FakeCallRepo())


def test_start_call_success(service: CallService):
    call = service.start_call(chat_id=1, initiator_id=1, to_user_id=2)
    assert call.status == "ringing"


def test_start_call_forbidden(service: CallService):
    with pytest.raises(PermissionDeniedError):
        service.start_call(chat_id=1, initiator_id=100, to_user_id=2)


def test_start_call_with_same_user(service: CallService):
    with pytest.raises(ValidationError):
        service.start_call(chat_id=1, initiator_id=1, to_user_id=1)


def test_start_call_fails_for_non_member_recipient(service: CallService):
    with pytest.raises(ValidationError):
        service.start_call(chat_id=1, initiator_id=1, to_user_id=100)


def test_add_signal_and_status(service: CallService):
    call = service.start_call(chat_id=1, initiator_id=1, to_user_id=2)
    service.add_signal(call_id=call.id, from_user_id=1, to_user_id=2, event_type="offer", payload="{}")
    updated = service.set_status(call_id=call.id, user_id=2, status="accepted")
    assert updated.status == "accepted"


def test_set_status_missing_call(service: CallService):
    with pytest.raises(NotFoundError):
        service.set_status(call_id=500, user_id=1, status="ended")


def test_add_signal_forbidden_for_sender(service: CallService):
    call = service.start_call(chat_id=1, initiator_id=1, to_user_id=2)
    with pytest.raises(PermissionDeniedError):
        service.add_signal(call_id=call.id, from_user_id=100, to_user_id=2, event_type="offer", payload="{}")


def test_add_signal_fails_for_missing_recipient(service: CallService):
    call = service.start_call(chat_id=1, initiator_id=1, to_user_id=2)
    with pytest.raises(ValidationError):
        service.add_signal(call_id=call.id, from_user_id=1, to_user_id=100, event_type="offer", payload="{}")


def test_set_status_forbidden(service: CallService):
    call = service.start_call(chat_id=1, initiator_id=1, to_user_id=2)
    with pytest.raises(PermissionDeniedError):
        service.set_status(call_id=call.id, user_id=100, status="ended")


def test_set_status_raises_if_update_missing():
    service = CallService(chat_repo=FakeChatRepo(), call_repo=FakeCallRepoNoUpdate())
    call = service.start_call(chat_id=1, initiator_id=1, to_user_id=2)
    with pytest.raises(NotFoundError):
        service.set_status(call_id=call.id, user_id=1, status="ended")
