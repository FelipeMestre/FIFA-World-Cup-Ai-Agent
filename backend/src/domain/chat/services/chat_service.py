import uuid

from src.domain.chat.exceptions.chat_exceptions import ChatServiceUnavailable
from src.domain.chat.model.message import Message
from src.domain.chat.services.tool_call_executor import ToolCallExecutor
from src.domain.chat.tools.registry import TOOL_REGISTRY
from src.infra.openrouter.exceptions import OpenRouterRequestFailed
from src.infra.openrouter.interfaces.openrouter_client_interface import OpenRouterClientInterface
from src.infra.openrouter.schemas import ChatCompletionResult, ToolLoopCapReached
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

DEFAULT_TOOL_SCHEMAS: list[dict] = [
    tool_definition.json_schema for tool_definition in TOOL_REGISTRY.values()
]


class ChatService:
    """Orchestrates a single chat turn: load history, run the bounded
    tool-execution loop against the LLM (delegated to `ToolCallExecutor`),
    persist the updated history.
    """

    def __init__(
        self,
        conversation_cache: ConversationCacheRepositoryInterface,
        openrouter_client: OpenRouterClientInterface,
    ) -> None:
        self._conversation_cache = conversation_cache
        self._tool_executor = ToolCallExecutor(openrouter_client)

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
            result = await self._tool_executor.run(
                completion_messages,
                tools if tools is not None else DEFAULT_TOOL_SCHEMAS,
            )
        except OpenRouterRequestFailed as exc:
            raise ChatServiceUnavailable(str(exc)) from exc

        reply_content = _reply_content(result)
        history.append(Message(role="assistant", content=reply_content))
        await self._conversation_cache.save_history(
            resolved_conversation_id, history, ttl_seconds=CONVERSATION_HISTORY_TTL_SECONDS
        )
        return resolved_conversation_id, reply_content


def _reply_content(result: ChatCompletionResult | ToolLoopCapReached) -> str:
    """On a normal completion, the assistant's final content. On a
    cap-trip, the best-effort partial content plus the clarification ask --
    always shown to the user, never silently discarded and never replaced by
    a raw error.
    """
    if isinstance(result, ToolLoopCapReached):
        return f"{result.partial_content}\n\n{result.clarification}".strip()
    return result.content
