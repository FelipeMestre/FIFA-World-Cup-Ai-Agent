import json
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.auth.services.dependencies import JwtDataDep
from src.api.v1.chat.dtos.chat_dtos import WIDGET_TYPE_TO_PART_CLASS, MessagePart, TextPart
from src.api.v1.chat.dtos.conversation_dtos import (
    ConversationMessageDto,
    ConversationMessagesResponse,
    ConversationSummaryDto,
    SendMessageRequest,
    SendMessageResponse,
    UpdateConversationTitleRequest,
)
from src.api.v1.chat.services.chat_service_factory import build_chat_service
from src.api.v1.chat.sse import client_message
from src.domain.chat.exceptions.chat_exceptions import (
    TURN_ALREADY_IN_PROGRESS_DETAIL,
    ConversationOwnershipError,
    TurnAlreadyInProgress,
)
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
from src.infra.task_queue.chat_streams import (
    TURN_IN_PROGRESS_TTL_SECONDS,
    is_stream_cursor,
    last_stream_cursor,
    resume_turn_cursor,
    serialize_user_message_event,
    turn_in_progress_key,
    turn_stream_key,
)
from src.infra.task_queue.pool import enqueue_chat_reply

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
        icon=conversation.icon,
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


@router.post(
    "/{conversation_id}/messages",
    response_model=SendMessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Send a message in a conversation",
    description="Persists the user message, publishes it on the conversation's turn "
    "stream, and enqueues reply generation. The reply itself, and any live-published "
    "user-message echo, are read back via `GET /conversations/{id}/events` (SSE). "
    "Returns 409 while a reply is already being generated for this conversation, and 403 "
    "for a conversation owned by another user.",
    responses={
        status.HTTP_403_FORBIDDEN: {"description": "Conversation owned by another user"},
        status.HTTP_409_CONFLICT: {"description": "A reply is already being generated"},
    },
)
async def send_message(
    conversation_id: UUID,
    payload: SendMessageRequest,
    session: SessionDep,
    jwt_data: JwtDataDep,
) -> SendMessageResponse:
    user_id = int(jwt_data["sub"])
    chat_service = build_chat_service(session)
    try:
        conversation = await chat_service.start_turn(
            conversation_id=conversation_id, user_id=user_id, first_message=payload.content
        )
        cursor = await last_stream_cursor(str(conversation_id))
        reserved = await redis_client.set(
            turn_in_progress_key(str(conversation_id)),
            cursor,
            nx=True,
            ex=TURN_IN_PROGRESS_TTL_SECONDS,
        )
        if not reserved:
            raise TurnAlreadyInProgress()
    except ConversationOwnershipError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Conversation not found"
        ) from exc
    except TurnAlreadyInProgress as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=TURN_ALREADY_IN_PROGRESS_DETAIL
        ) from exc

    user_message = await chat_service.persist_user_message(conversation_id, payload.content)
    await redis_client.xadd(
        turn_stream_key(str(conversation_id)),
        serialize_user_message_event(
            str(conversation.id), user_message.id, payload.content, conversation.title
        ),
    )
    await enqueue_chat_reply(str(conversation_id), user_id, payload.content, user_message.id)

    return SendMessageResponse(conversation_id=conversation.id, message_id=user_message.id)


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


# Same blocking window the old live socket's `_pump` used -- long enough to
# avoid busy-polling Redis, short enough that a disconnect (checked once per
# iteration) or a keep-alive comment is never more than ~1s late.
_READ_BLOCK_MS = 1_000

# ~15 consecutive empty `XREAD` polls (~15s at `_READ_BLOCK_MS`) before a
# keep-alive comment is sent -- purely an infra-correctness concern: a
# reverse proxy or load balancer sitting between the client and this
# response can decide an idle connection is dead and close it.
_KEEPALIVE_EMPTY_POLLS = 15


async def _conversation_events(
    request: Request, turn_key: str, turn_cursor: str
) -> AsyncIterator[str]:
    empty_polls = 0
    while True:
        if await request.is_disconnected():
            return

        response = await redis_client.xread({turn_key: turn_cursor}, block=_READ_BLOCK_MS)
        if not response:
            empty_polls += 1
            if empty_polls >= _KEEPALIVE_EMPTY_POLLS:
                yield ": keep-alive\n\n"
                empty_polls = 0
            continue
        empty_polls = 0

        for _stream_name, entries in response:
            for entry_id, fields in entries:
                turn_cursor = entry_id
                data = client_message(entry_id, fields["event_type"], json.loads(fields["payload"]))
                yield f"id: {turn_cursor}\nevent: turn\ndata: {json.dumps(data)}\n\n"


@router.get(
    "/{conversation_id}/events",
    summary="Turn event stream for a conversation",
    description="Server-Sent Events replacement for the old live WebSocket's receive side -- "
    "single-key `XREAD` over this conversation's turn stream only. `event: turn` frames carry "
    "the same shape the old socket sent. Account-wide events (a conversation being created "
    "or a background categorization job finishing) are delivered separately over "
    "`GET /users/events`, not on this connection -- see `user_events_router.py`. Resumes from "
    "the `Last-Event-ID` header when present and valid. Returns 404 for both a missing "
    "conversation and one owned by another user alike -- existence is never leaked to a "
    "non-owner, matching `GET /conversations/{id}/messages`'s convention (not "
    "`POST .../messages`'s 403, which is this router's write-path convention).",
)
async def stream_conversation_events(
    conversation_id: UUID,
    request: Request,
    conversation_repo: ConversationRepositoryDep,
    jwt_data: JwtDataDep,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    user_id = int(jwt_data["sub"])
    conversation = await conversation_repo.get_owned(conversation_id, user_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    turn_key = turn_stream_key(str(conversation_id))
    if last_event_id is not None and is_stream_cursor(last_event_id):
        turn_cursor = last_event_id
    else:
        turn_cursor = await resume_turn_cursor(str(conversation_id))

    return StreamingResponse(
        _conversation_events(request, turn_key, turn_cursor),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Reverse proxies like nginx buffer a response by default, which
            # would defeat SSE entirely -- this tells them not to. Has no
            # effect locally, but matters once this sits behind one.
            "X-Accel-Buffering": "no",
        },
    )
