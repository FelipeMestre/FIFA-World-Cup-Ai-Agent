from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from src.api.v1.chat.dtos.chat_dtos import MessagePart

# No hard limit exists on the underlying chat turn itself -- this caps the
# HTTP request body to a sane size instead of leaving it unbounded.
_SEND_MESSAGE_MAX_LENGTH = 8000


class ConversationSummaryDto(BaseModel):
    """One row in the sidebar conversation list (`GET /conversations`) or
    the response of a title rename (`PATCH /conversations/{id}`).
    `is_generating` reflects `chat:turn-in-progress:{id}` at the moment of
    the request -- a snapshot, not a live subscription; the sidebar only
    sees it change on its next fetch."""

    id: UUID
    title: str
    icon: str | None = None
    updated_at: datetime
    created_at: datetime
    is_generating: bool = False


class UpdateConversationTitleRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class ConversationMessageDto(BaseModel):
    """One `ChatMessage` replayed for `GET /conversations/{id}/messages`.
    `parts` mirrors the shape the SSE `message_done` event's `parts` already
    carries, for rendering consistency between a live turn and a reload."""

    role: Literal["user", "assistant"]
    parts: list[MessagePart]
    created_at: datetime


class ConversationMessagesResponse(BaseModel):
    """`last_turn_failure` is only ever set when the failed user message is
    still the last message in the conversation -- a later retry (a new
    `chat_message` row) makes an older failure stale and it is never
    surfaced again, even though its `chat_turn_failure` row still exists."""

    conversation_id: UUID
    title: str
    messages: list[ConversationMessageDto]
    last_turn_failure: str | None = None


class SendMessageRequest(BaseModel):
    """Body of `POST /conversations/{id}/messages`."""

    content: str = Field(min_length=1, max_length=_SEND_MESSAGE_MAX_LENGTH)

    @field_validator("content")
    @classmethod
    def _strip_and_require_non_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("content must not be blank")
        return stripped


class SendMessageResponse(BaseModel):
    """202 ack for `POST /conversations/{id}/messages` -- reply generation
    itself is asynchronous (enqueued, not returned here); the caller reads
    the SSE stream (`GET /conversations/{id}/events`) for the actual reply."""

    conversation_id: UUID
    message_id: int
