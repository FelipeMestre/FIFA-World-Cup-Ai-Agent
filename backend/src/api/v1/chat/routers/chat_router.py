from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.auth.services.dependencies import JwtDataDep
from src.api.v1.chat.dtos.chat_dtos import SendMessageAckResponse, SendMessageRequest
from src.domain.chat.exceptions.chat_exceptions import ConversationOwnershipError
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
from src.infra.redis.config import redis_client
from src.infra.redis.interfaces.conversation_cache_repository_interface import (
    ConversationCacheRepositoryInterface,
)
from src.infra.redis.repositories.conversation_cache_repository import (
    get_conversation_cache_repository,
)
from src.infra.task_queue.chat_tasks import TURN_IN_PROGRESS_TTL_SECONDS, turn_in_progress_key
from src.infra.task_queue.pool import enqueue_chat_reply

router = APIRouter(prefix="/chat", tags=["chat"])

_TURN_ALREADY_IN_PROGRESS_DETAIL = "A reply is already being generated for this conversation"


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
    status_code=status.HTTP_202_ACCEPTED,
    summary="Send a chat message",
    description=(
        "Persists the user's message and enqueues `generate_chat_reply_task` to generate "
        "the assistant's reply in the background -- this endpoint does not stream the "
        "reply itself. Connect to `GET /conversations/{id}/watch` right after this "
        "returns to observe the reply as it is generated."
    ),
)
async def send_message(
    payload: SendMessageRequest,
    chat_service: ChatServiceDep,
    jwt_data: JwtDataDep,
) -> SendMessageAckResponse:
    user_id = int(jwt_data["sub"])
    try:
        conversation = await chat_service.start_turn(
            conversation_id=payload.conversation_id,
            user_id=user_id,
            first_message=payload.message,
        )
    except ConversationOwnershipError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    # The one-turn-per-conversation guard: `SET NX` is the actual authority
    # here (see chat_tasks.py's module docstring) -- the job itself no
    # longer attempts its own reservation, it only refreshes and clears
    # this flag.
    reserved = await redis_client.set(
        turn_in_progress_key(str(payload.conversation_id)),
        "1",
        nx=True,
        ex=TURN_IN_PROGRESS_TTL_SECONDS,
    )
    if not reserved:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=_TURN_ALREADY_IN_PROGRESS_DETAIL
        )

    user_message = await chat_service.persist_user_message(payload.conversation_id, payload.message)
    await enqueue_chat_reply(
        str(payload.conversation_id), user_id, payload.message, user_message.id
    )

    return SendMessageAckResponse(conversation_id=str(conversation.id), title=conversation.title)
