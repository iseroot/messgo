from enum import StrEnum


class ChatType(StrEnum):
    """Тип чата."""

    DIRECT = "direct"
    GROUP = "group"


class MessageType(StrEnum):
    """Тип сообщения."""

    TEXT = "text"
    SYSTEM = "system"


class MessageStatus(StrEnum):
    """Статус доставки сообщения."""

    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"


class CallStatus(StrEnum):
    """Статус звонка."""

    RINGING = "ringing"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    ENDED = "ended"
    MISSED = "missed"


class PresenceStatus(StrEnum):
    """Статус присутствия."""

    ONLINE = "online"
    OFFLINE = "offline"
