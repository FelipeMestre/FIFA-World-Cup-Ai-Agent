from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.auth.services.dependencies import JwtDataDep
from src.api.v1.chat.dtos.chat_dtos import WIDGET_TYPE_TO_PART_CLASS, MessagePart, TextPart
from src.api.v1.chat.dtos.conversation_dtos import (
    ConversationMessageDto,
    ConversationMessagesResponse,
    ConversationSummaryDto,
    UpdateConversationTitleRequest,
)
from src.domain.chat.model.chat_message import ChatMessage
from src.domain.chat.model.chat_message_widget import ChatMessageWidget
from src.domain.chat.model.conversation import Conversation
from src.infra.postgres.config import get_db
from src.infra.postgres.interfaces.chat_message_repository_interface import (
    ChatMessageRepositoryInterface,
)
from src.infra.postgres.interfaces.conversation_repository_interface import (
    ConversationRepositoryInterface,
)
from src.infra.postgres.repositories.chat_message_repository import get_chat_message_repository
from src.infra.postgres.repositories.conversation_repository import get_conversation_repository

router = APIRouter(prefix="/conversations", tags=["conversations"])

ConversationRepositoryDep = Annotated[
    ConversationRepositoryInterface, Depends(get_conversation_repository)
]
ChatMessageRepositoryDep = Annotated[
    ChatMessageRepositoryInterface, Depends(get_chat_message_repository)
]
SessionDep = Annotated[AsyncSession, Depends(get_db)]


def _to_summary_dto(conversation: Conversation) -> ConversationSummaryDto:
    return ConversationSummaryDto(
        id=conversation.id,
        title=conversation.title,
        updated_at=conversation.updated_at,
        created_at=conversation.created_at,
    )


def _widget_to_part(widget: ChatMessageWidget) -> MessagePart:
    part_class = WIDGET_TYPE_TO_PART_CLASS.get(widget.widget_type)
    if part_class is None:
        raise ValueError(f"No MessagePart mapped for widget_type={widget.widget_type!r}")
    return part_class(data=widget.data)


def _to_message_dto(message: ChatMessage) -> ConversationMessageDto:
    # Widgets first, then text -- the true interleaved order from the live
    # stream isn't persisted (chat_message.content is one flat final
    # string), so a reload can't reconstruct it exactly. Putting widgets
    # ahead of the text matches how a live turn actually reads: the widget
    # resolves during the tool call, before the model's prose about it.
    parts: list[MessagePart] = [_widget_to_part(widget) for widget in message.widgets]
    parts.append(TextPart(content=message.content))
    return ConversationMessageDto(role=message.role, parts=parts, created_at=message.created_at)


@router.get(
    "",
    response_model=list[ConversationSummaryDto],
    summary="List the current user's conversations",
    description="Returns the current user's conversations ordered by most-recent activity, "
    "for the sidebar.",
)
async def list_conversations(
    conversation_repo: ConversationRepositoryDep,
    jwt_data: JwtDataDep,
) -> list[ConversationSummaryDto]:
    user_id = int(jwt_data["sub"])
    conversations = await conversation_repo.list_for_user(user_id)
    return [_to_summary_dto(conversation) for conversation in conversations]


@router.patch(
    "/{conversation_id}",
    response_model=ConversationSummaryDto,
    summary="Rename a conversation",
    description="Updates a conversation's title. Returns 404 for a missing conversation and "
    "for one owned by another user alike -- existence is never leaked to a non-owner.",
)
async def update_conversation_title(
    conversation_id: UUID,
    payload: UpdateConversationTitleRequest,
    conversation_repo: ConversationRepositoryDep,
    session: SessionDep,
    jwt_data: JwtDataDep,
) -> ConversationSummaryDto:
    user_id = int(jwt_data["sub"])
    updated = await conversation_repo.update_title(conversation_id, user_id, payload.title)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    await session.commit()
    return _to_summary_dto(updated)


@router.get(
    "/{conversation_id}/messages",
    response_model=ConversationMessagesResponse,
    summary="Replay a conversation's full message history",
    description="Always reads Postgres directly, never Redis -- the cache only holds flat "
    "role+content for the LLM prompt path and has no widget data, so a cache-first reload "
    "would silently drop widgets on a hit.",
)
async def get_conversation_messages(
    conversation_id: UUID,
    conversation_repo: ConversationRepositoryDep,
    chat_message_repo: ChatMessageRepositoryDep,
    jwt_data: JwtDataDep,
) -> ConversationMessagesResponse:
    user_id = int(jwt_data["sub"])
    conversation = await conversation_repo.get_owned(conversation_id, user_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    messages = await chat_message_repo.list_for_conversation(conversation_id, user_id)
    return ConversationMessagesResponse(
        conversation_id=conversation.id,
        title=conversation.title,
        messages=[_to_message_dto(message) for message in messages],
    )
