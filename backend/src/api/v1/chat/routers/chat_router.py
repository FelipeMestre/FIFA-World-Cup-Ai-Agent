from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from src.api.v1.auth.services.dependencies import JwtDataDep
from src.api.v1.chat.dtos.chat_dtos import (
    CapReachedEventDto,
    ChatStreamEvent,
    ContentDeltaEventDto,
    ErrorEventDto,
    MessageDoneEventDto,
    ReasoningDeltaEventDto,
    SendMessageRequest,
    TextPart,
    ToolCallEventDto,
)
from src.domain.chat.exceptions.chat_exceptions import ChatServiceUnavailable
from src.domain.chat.services.chat_service import (
    CapReachedEvent,
    ChatService,
    ChatTurnEvent,
    ContentDeltaEvent,
    MessageDoneEvent,
    ReasoningDeltaEvent,
    ToolCallRequestedEvent,
)
from src.infra.openrouter.client import get_openrouter_client
from src.infra.openrouter.interfaces.openrouter_client_interface import OpenRouterClientInterface
from src.infra.redis.interfaces.conversation_cache_repository_interface import (
    ConversationCacheRepositoryInterface,
)
from src.infra.redis.repositories.conversation_cache_repository import (
    get_conversation_cache_repository,
)

router = APIRouter(prefix="/chat", tags=["chat"])

_UNAVAILABLE_ERROR_DETAIL = "The chat assistant is temporarily unavailable"


def get_chat_service(
    conversation_cache: Annotated[
        ConversationCacheRepositoryInterface, Depends(get_conversation_cache_repository)
    ],
    openrouter_client: Annotated[OpenRouterClientInterface, Depends(get_openrouter_client)],
) -> ChatService:
    return ChatService(conversation_cache, openrouter_client)


ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]


@router.post(
    "/messages",
    status_code=200,
    summary="Send a chat message",
    description=(
        "Sends a user message to the World Cup AI Scout assistant and streams its reply "
        "via Server-Sent Events (`reasoning_delta`, `content_delta`, `tool_call`, "
        "`cap_reached`, `message_done`, `error`)."
    ),
)
async def send_message(
    payload: SendMessageRequest,
    chat_service: ChatServiceDep,
    _: JwtDataDep,
) -> StreamingResponse:
    return StreamingResponse(
        _stream_chat_events(chat_service, payload.conversation_id, payload.message),
        media_type="text/event-stream",
    )


async def _stream_chat_events(
    chat_service: ChatService, conversation_id: str | None, message: str
) -> AsyncIterator[bytes]:
    try:
        async for event in chat_service.send_message(
            conversation_id=conversation_id, user_message=message
        ):
            yield _format_sse(_to_dto(event))
    except ChatServiceUnavailable:
        yield _format_sse(ErrorEventDto(detail=_UNAVAILABLE_ERROR_DETAIL))


def _to_dto(event: ChatTurnEvent) -> ChatStreamEvent:
    if isinstance(event, ReasoningDeltaEvent):
        return ReasoningDeltaEventDto(content=event.content)
    if isinstance(event, ContentDeltaEvent):
        return ContentDeltaEventDto(content=event.content)
    if isinstance(event, ToolCallRequestedEvent):
        return ToolCallEventDto(name=event.name)
    if isinstance(event, CapReachedEvent):
        return CapReachedEventDto(content=event.content, clarification=event.clarification)
    if isinstance(event, MessageDoneEvent):
        return MessageDoneEventDto(
            conversation_id=event.conversation_id,
            parts=[TextPart(content=event.content)],
            model=event.model,
        )
    raise ValueError(f"Unhandled chat stream event: {event!r}")


def _format_sse(dto: ChatStreamEvent) -> bytes:
    payload = dto.model_dump_json(exclude={"type"})
    return f"event: {dto.type.value}\ndata: {payload}\n\n".encode()
