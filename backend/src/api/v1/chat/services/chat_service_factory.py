"""Shared `ChatService` construction for the chat routers. Currently just the
`POST /conversations/{id}/messages` send endpoint (`conversation_router.py`),
but kept as its own factory rather than inlined there (see AGENTS.md's
application-service guidance for the api layer: logic reusable across
controllers, not a use-case orchestration itself) since it previously also
backed the now-removed live WebSocket route and may again back another
caller.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.chat.services.chat_service import ChatService
from src.domain.chat.tools.registry import build_tool_registry
from src.infra.openrouter.client import get_openrouter_client
from src.infra.postgres.repositories.chat_message_repository import get_chat_message_repository
from src.infra.postgres.repositories.conversation_repository import get_conversation_repository
from src.infra.postgres.repositories.match_analytics_repository import (
    get_match_analytics_repository,
)
from src.infra.postgres.repositories.player_analytics_repository import (
    get_player_analytics_repository,
)
from src.infra.postgres.repositories.team_analytics_repository import get_team_analytics_repository
from src.infra.redis.config import redis_client
from src.infra.redis.repositories.conversation_cache_repository import (
    get_conversation_cache_repository,
)


def build_chat_service(session: AsyncSession) -> ChatService:
    return ChatService(
        conversation_cache=get_conversation_cache_repository(redis_client),
        openrouter_client=get_openrouter_client(),
        tool_registry=build_tool_registry(
            get_team_analytics_repository(session),
            get_player_analytics_repository(session),
            get_match_analytics_repository(session),
        ),
        conversation_repo=get_conversation_repository(session),
        chat_message_repo=get_chat_message_repository(session),
        session=session,
    )
