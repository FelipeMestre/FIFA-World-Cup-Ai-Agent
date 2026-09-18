import uuid

from src.domain.chat.exceptions.chat_exceptions import ChatServiceUnavailable
from src.domain.chat.model.message import Message
from src.infra.openrouter.exceptions import OpenRouterRequestFailed
from src.infra.openrouter.interfaces.openrouter_client_interface import OpenRouterClientInterface
from src.infra.redis.interfaces.conversation_cache_repository_interface import (
    ConversationCacheRepositoryInterface,
)

SYSTEM_PROMPT = (
    "You are the World Cup AI Scout assistant for a FIFA World Cup 2026 analytics app. "
    "You answer questions about teams, matches, and players using the data "
    "available in this application. IMPORTANT: the underlying tournament dataset "
    "is a simulated, synthetic FIFA World Cup 2026 -- not a record of real-world "
    "results. Never present any team, match, or player statistic as real-world "
    "fact. Always treat it as data from this app's simulated dataset, and say so "
    "if the user seems to be asking for real-world accuracy."
)

CONVERSATION_HISTORY_TTL_SECONDS = 60 * 60 * 24  # 24h


class ChatService:
    """Orchestrates a single chat turn: load history, call the LLM, persist
    the updated history. `tools` is threaded through untouched as an explicit
    extension point for a future tool-calling phase (team/match/player
    analytics tools) -- no tool implementations exist yet.
    """

    def __init__(
        self,
        conversation_cache: ConversationCacheRepositoryInterface,
        openrouter_client: OpenRouterClientInterface,
    ) -> None:
        self._conversation_cache = conversation_cache
        self._openrouter_client = openrouter_client

    async def send_message(
        self,
        conversation_id: str | None,
        user_message: str,
        tools: list[dict] | None = None,
    ) -> tuple[str, str]:
        resolved_conversation_id = conversation_id or str(uuid.uuid4())
        history = await self._conversation_cache.get_history(resolved_conversation_id)
        history.append(Message(role="user", content=user_message))

        completion_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        completion_messages.extend({"role": m.role, "content": m.content} for m in history)

        try:
            reply_content = await self._openrouter_client.create_chat_completion(
                messages=completion_messages,
                tools=tools,
            )
        except OpenRouterRequestFailed as exc:
            raise ChatServiceUnavailable(str(exc)) from exc

        history.append(Message(role="assistant", content=reply_content))
        await self._conversation_cache.save_history(
            resolved_conversation_id, history, ttl_seconds=CONVERSATION_HISTORY_TTL_SECONDS
        )
        return resolved_conversation_id, reply_content
