from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.auth.services.dependencies import JwtDataDep
from src.api.v1.chat.dtos.chat_dtos import ErrorEventDto, SendMessageRequest
from src.api.v1.chat.sse import format_sse, to_dto
from src.domain.chat.exceptions.chat_exceptions import (
    ChatServiceUnavailable,
    ConversationOwnershipError,
)
from src.domain.chat.services.chat_service import ChatService
from src.domain.chat.tools.registry import ToolDefinition, build_tool_registry
from src.infra.openrouter.client import get_openrouter_client
from src.infra.openrouter.interfaces.openrouter_client_interface import OpenRouterClientInterface
from src.infra.postgres.config import get_db
from src.infra.postgres.interfaces.chat_message_repository_interface import (
    ChatMessageRepositoryInterface,
)
from src.infra.postgres.interfaces.conversation_repository_interface import (
    ConversationRepositoryInterface,
)
from src.infra.postgres.interfaces.match_analytics_repository_interface import (
    MatchAnalyticsRepositoryInterface,
)
from src.infra.postgres.interfaces.player_analytics_repository_interface import (
    PlayerAnalyticsRepositoryInterface,
)
from src.infra.postgres.interfaces.team_analytics_repository_interface import (
    TeamAnalyticsRepositoryInterface,
)
from src.infra.postgres.repositories.chat_message_repository import get_chat_message_repository
from src.infra.postgres.repositories.conversation_repository import get_conversation_repository
from src.infra.postgres.repositories.match_analytics_repository import (
    get_match_analytics_repository,
)
from src.infra.postgres.repositories.player_analytics_repository import (
    get_player_analytics_repository,
)
from src.infra.postgres.repositories.team_analytics_repository import (
    get_team_analytics_repository,
)
from src.infra.redis.interfaces.conversation_cache_repository_interface import (
    ConversationCacheRepositoryInterface,
)
from src.infra.redis.repositories.conversation_cache_repository import (
    get_conversation_cache_repository,
)

router = APIRouter(prefix="/chat", tags=["chat"])

_UNAVAILABLE_ERROR_DETAIL = "The chat assistant is temporarily unavailable"


def get_tool_registry(
    team_analytics_repository: Annotated[
        TeamAnalyticsRepositoryInterface, Depends(get_team_analytics_repository)
    ],
    player_analytics_repository: Annotated[
        PlayerAnalyticsRepositoryInterface, Depends(get_player_analytics_repository)
    ],
    match_analytics_repository: Annotated[
        MatchAnalyticsRepositoryInterface, Depends(get_match_analytics_repository)
    ],
) -> dict[str, ToolDefinition]:
    return build_tool_registry(
        team_analytics_repository, player_analytics_repository, match_analytics_repository
    )


def get_chat_service(
    conversation_cache: Annotated[
        ConversationCacheRepositoryInterface, Depends(get_conversation_cache_repository)
    ],
    openrouter_client: Annotated[OpenRouterClientInterface, Depends(get_openrouter_client)],
    tool_registry: Annotated[dict[str, ToolDefinition], Depends(get_tool_registry)],
    conversation_repository: Annotated[
        ConversationRepositoryInterface, Depends(get_conversation_repository)
    ],
    chat_message_repository: Annotated[
        ChatMessageRepositoryInterface, Depends(get_chat_message_repository)
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ChatService:
    return ChatService(
        conversation_cache,
        openrouter_client,
        tool_registry,
        conversation_repository,
        chat_message_repository,
        session,
    )


ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]


@router.post(
    "/messages",
    status_code=200,
    summary="Send a chat message",
    description=(
        "Sends a user message to the World Cup AI Scout assistant and streams its reply "
        "via Server-Sent Events (`reasoning_delta`, `content_delta`, `tool_call`, "
        "`widget_ready`, `cap_reached`, `message_done`, `error`)."
    ),
)
async def send_message(
    payload: SendMessageRequest,
    chat_service: ChatServiceDep,
    jwt_data: JwtDataDep,
) -> StreamingResponse:
    user_id = int(jwt_data["sub"])
    try:
        await chat_service.start_turn(
            conversation_id=payload.conversation_id,
            user_id=user_id,
            first_message=payload.message,
        )
    except ConversationOwnershipError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    return StreamingResponse(
        _stream_chat_events(chat_service, payload.conversation_id, user_id, payload.message),
        media_type="text/event-stream",
    )


async def _stream_chat_events(
    chat_service: ChatService, conversation_id: UUID, user_id: int, message: str
) -> AsyncIterator[bytes]:
    try:
        async for event in chat_service.send_message(
            conversation_id=conversation_id, user_id=user_id, user_message=message
        ):
            yield format_sse(to_dto(event))
    except ChatServiceUnavailable:
        yield format_sse(ErrorEventDto(detail=_UNAVAILABLE_ERROR_DETAIL))
