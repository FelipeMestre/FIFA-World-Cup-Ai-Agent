import uuid
from collections.abc import AsyncIterator

from src.domain.chat.exceptions.chat_exceptions import ChatServiceUnavailable
from src.domain.chat.model.message import Message
from src.infra.openrouter.exceptions import OpenRouterRequestFailed
from src.infra.openrouter.interfaces.openrouter_client_interface import OpenRouterClientInterface
from src.infra.openrouter.schemas import (
    ChatCompletionChunk,
    ChatCompletionResult,
    FinishReason,
    ToolCall,
)
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
            chunks = self._openrouter_client.create_chat_completion(
                messages=completion_messages,
                tools=tools,
            )
            result = await _aggregate_chat_completion(chunks)
        except OpenRouterRequestFailed as exc:
            raise ChatServiceUnavailable(str(exc)) from exc

        reply_content = result.content
        history.append(Message(role="assistant", content=reply_content))
        await self._conversation_cache.save_history(
            resolved_conversation_id, history, ttl_seconds=CONVERSATION_HISTORY_TTL_SECONDS
        )
        return resolved_conversation_id, reply_content


async def _aggregate_chat_completion(
    chunks: AsyncIterator[ChatCompletionChunk],
) -> ChatCompletionResult:
    """Consume the client's live chunk stream and build one aggregated
    result. Stands in for the tool-execution loop's own aggregation until
    PR2 introduces it -- keeps the plain-message round trip working exactly
    as before from the outside while the client itself now streams.
    """
    content_parts: list[str] = []
    reasoning_parts: list[str] = []
    tool_calls: list[ToolCall] = []
    finish_reason: FinishReason | None = None
    model: str | None = None

    async for chunk in chunks:
        if chunk.delta_content:
            content_parts.append(chunk.delta_content)
        if chunk.delta_reasoning:
            reasoning_parts.append(chunk.delta_reasoning)
        if chunk.tool_calls is not None:
            tool_calls = chunk.tool_calls
        if chunk.finish_reason is not None:
            finish_reason = chunk.finish_reason
        if chunk.model is not None:
            model = chunk.model

    if finish_reason is None or model is None:
        raise OpenRouterRequestFailed(None, "Unexpected response shape")

    return ChatCompletionResult(
        content="".join(content_parts),
        reasoning="".join(reasoning_parts),
        tool_calls=tool_calls,
        finish_reason=finish_reason,
        model=model,
    )
