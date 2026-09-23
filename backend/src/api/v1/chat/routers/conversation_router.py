import json
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.auth.services.dependencies import JwtDataDep
from src.api.v1.chat.dtos.chat_dtos import WIDGET_TYPE_TO_PART_CLASS, MessagePart, TextPart
from src.api.v1.chat.dtos.conversation_dtos import (
    ConversationMessageDto,
    ConversationMessagesResponse,
    ConversationSummaryDto,
    UpdateConversationTitleRequest,
)
from src.api.v1.chat.sse import format_sse, is_terminal_event_type, redis_entry_to_dto
from src.domain.chat.model.chat_message import ChatMessage
from src.domain.chat.model.chat_message_widget import ChatMessageWidget
from src.domain.chat.model.conversation import Conversation
from src.infra.postgres.config import get_db
from src.infra.postgres.interfaces.chat_message_repository_interface import (
    ChatMessageRepositoryInterface,
)
from src.infra.postgres.interfaces.chat_turn_failure_repository_interface import (
    ChatTurnFailureRepositoryInterface,
)
from src.infra.postgres.interfaces.conversation_repository_interface import (
    ConversationRepositoryInterface,
)
from src.infra.postgres.repositories.chat_message_repository import get_chat_message_repository
from src.infra.postgres.repositories.chat_turn_failure_repository import (
    get_chat_turn_failure_repository,
)
from src.infra.postgres.repositories.conversation_repository import get_conversation_repository
from src.infra.redis.config import redis_client
from src.infra.task_queue.chat_tasks import turn_in_progress_key, turn_stream_key

# How long to wait for a new stream entry before re-checking whether the
# turn is still marked in-progress. Not a hard cap on total watch time --
# just how often to notice a job that vanished without a clean terminal
# write (crashed, or its in-progress TTL lapsed).
_WATCH_POLL_TIMEOUT_MS = 10_000

router = APIRouter(prefix="/conversations", tags=["conversations"])

ConversationRepositoryDep = Annotated[
    ConversationRepositoryInterface, Depends(get_conversation_repository)
]
ChatMessageRepositoryDep = Annotated[
    ChatMessageRepositoryInterface, Depends(get_chat_message_repository)
]
ChatTurnFailureRepositoryDep = Annotated[
    ChatTurnFailureRepositoryInterface, Depends(get_chat_turn_failure_repository)
]
SessionDep = Annotated[AsyncSession, Depends(get_db)]


def _to_summary_dto(conversation: Conversation, is_generating: bool) -> ConversationSummaryDto:
    return ConversationSummaryDto(
        id=conversation.id,
        title=conversation.title,
        updated_at=conversation.updated_at,
        created_at=conversation.created_at,
        is_generating=is_generating,
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
    if not conversations:
        return []

    # One MGET for the whole list instead of one EXISTS per row -- the
    # sidebar renders every conversation on every fetch, so this avoids an
    # N-round-trip fan-out to Redis.
    flags = await redis_client.mget(
        [turn_in_progress_key(str(conversation.id)) for conversation in conversations]
    )
    return [
        _to_summary_dto(conversation, is_generating=flag is not None)
        for conversation, flag in zip(conversations, flags, strict=True)
    ]


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
    is_generating = await redis_client.exists(turn_in_progress_key(str(updated.id)))
    return _to_summary_dto(updated, is_generating=bool(is_generating))


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
    chat_turn_failure_repo: ChatTurnFailureRepositoryDep,
    jwt_data: JwtDataDep,
) -> ConversationMessagesResponse:
    user_id = int(jwt_data["sub"])
    conversation = await conversation_repo.get_owned(conversation_id, user_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    messages = await chat_message_repo.list_for_conversation(conversation_id, user_id)

    # Only the last message can still have a live failure -- a later
    # message (a retry, or an assistant reply that did land) means an
    # older `chat_turn_failure` row, if any, is stale and stays hidden.
    last_turn_failure = None
    if messages and messages[-1].role == "user":
        last_turn_failure = await chat_turn_failure_repo.get_detail_for_message(messages[-1].id)

    return ConversationMessagesResponse(
        conversation_id=conversation.id,
        title=conversation.title,
        last_turn_failure=last_turn_failure,
        messages=[_to_message_dto(message) for message in messages],
    )


@router.get(
    "/{conversation_id}/watch",
    summary="Reattach to a conversation's in-progress turn, if any",
    description="Streams the same SSE vocabulary as `POST /chat/messages` "
    "(`reasoning_delta`, `content_delta`, `tool_call`, `widget_ready`, `cap_reached`, "
    "`message_done`, `error`), sourced from `generate_chat_reply_task`'s Redis stream "
    "instead of a live generation -- any number of watchers can attach or detach without "
    "affecting the job itself. Catches up on everything already generated, then continues "
    "live until a terminal event lands. Responds 204 with no body if no turn is currently "
    "in progress for this conversation -- callers should fall back to the ordinary reload "
    "endpoint in that case, not treat 204 as an error.",
)
async def watch_conversation_turn(
    conversation_id: UUID,
    conversation_repo: ConversationRepositoryDep,
    jwt_data: JwtDataDep,
) -> Response:
    user_id = int(jwt_data["sub"])
    conversation = await conversation_repo.get_owned(conversation_id, user_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    if not await redis_client.exists(turn_in_progress_key(str(conversation_id))):
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return StreamingResponse(
        _watch_turn_stream(str(conversation_id)), media_type="text/event-stream"
    )


async def _watch_turn_stream(conversation_id: str) -> AsyncIterator[bytes]:
    stream_key = turn_stream_key(conversation_id)
    progress_key = turn_in_progress_key(conversation_id)
    last_id = "0"  # start from the beginning -- catch up on everything already generated

    while True:
        response = await redis_client.xread({stream_key: last_id}, block=_WATCH_POLL_TIMEOUT_MS)
        if not response:
            # No new entry within the poll window. If the job is no longer
            # marked in-progress, it ended without a clean terminal write
            # (crashed, or the flag's own TTL lapsed) -- stop waiting rather
            # than hold the connection open forever.
            if not await redis_client.exists(progress_key):
                return
            continue

        _stream_name, entries = response[0]
        for entry_id, fields in entries:
            last_id = entry_id
            event_type = fields["event_type"]
            dto = redis_entry_to_dto(event_type, json.loads(fields["payload"]))
            yield format_sse(dto)
            if is_terminal_event_type(event_type):
                return
