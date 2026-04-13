from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    display_name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=128)
    invite_code: str = Field(min_length=6, max_length=120)


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=128)


class InviteCreateRequest(BaseModel):
    code: str = Field(min_length=6, max_length=120)
    ttl_hours: int = Field(default=72, ge=1, le=720)
    max_uses: int = Field(default=5, ge=1, le=100)


class ChatCreateRequest(BaseModel):
    type: str = Field(pattern="^(direct|group)$")
    peer_id: int | None = None
    title: str | None = None
    member_ids: list[int] = Field(default_factory=list)


class MessageCreateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    reply_to_message_id: int | None = None


class CallStatusRequest(BaseModel):
    status: str = Field(pattern="^(accepted|declined|ended|missed)$")


class CallStartRequest(BaseModel):
    chat_id: int
    to_user_id: int


class CallSignalRequest(BaseModel):
    call_id: int
    to_user_id: int
    type: str
    payload: str


class UserView(BaseModel):
    id: int
    username: str
    display_name: str


class ChatView(BaseModel):
    id: int
    type: str
    title: str | None
    created_at: datetime


class MessageView(BaseModel):
    id: int
    chat_id: int
    sender_id: int
    text: str
    status: str
    created_at: datetime
