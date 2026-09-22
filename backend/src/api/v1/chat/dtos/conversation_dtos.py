from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from src.api.v1.chat.dtos.chat_dtos import MessagePart


class ConversationSummaryDto(BaseModel):
    """One row in the sidebar conversation list (`GET /conversations`) or
    the response of a title rename (`PATCH /conversations/{id}`)."""

    id: UUID
    title: str
    updated_at: datetime
    created_at: datetime


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
    conversation_id: UUID
    title: str
    messages: list[ConversationMessageDto]
