import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

from src.domain.chat.exceptions.chat_exceptions import ChatServiceUnavailable
from src.domain.chat.model.message import Message
from src.domain.chat.services.tool_call_executor import (
    ContentDeltaEvent,
    ReasoningDeltaEvent,
    ToolCallExecutor,
    ToolCallRequestedEvent,
    ToolWidgetResult,
    TurnResolvedEvent,
    WidgetReadyEvent,
)
from src.domain.chat.tools.registry import ALL_TOOL_SCHEMAS, ToolDefinition
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

DEFAULT_TOOL_SCHEMAS: list[dict] = ALL_TOOL_SCHEMAS


@dataclass(frozen=True)
class CapReachedEvent:
    """The tool-execution loop's iteration cap tripped. `content` is the
    best-effort partial content accumulated so far; `clarification` is the
    clarification-ask text appended after it. Always followed by a
    `MessageDoneEvent` carrying the same combined text.
    """

    content: str
    clarification: str


@dataclass(frozen=True)
class MessageDoneEvent:
    """Terminal event for one chat turn: the conversation has been
    persisted and `content` is the final text shown to the user (either the
    assistant's normal reply, or the cap-trip's partial content plus
    clarification).

    `content_segments` is what a full-message render (e.g. the SSE `parts`
    array, or a page reload replaying this message) should actually be
    built from -- text and widgets in the order they occurred, matching
    what was already shown live via `WidgetReadyEvent`. It is *not* just
    `[content, *widgets]`: on a normal completion this is `ToolCallExecutor`'s
    own `content_segments`, preserving true interleaving; on a cap-trip it
    collapses to a single `content` segment (widgets from an incomplete,
    already-degraded turn aren't worth threading through -- the frontend
    ignores these `parts` in that case anyway, keeping its own
    already-rendered content instead).
    """

    conversation_id: str
    content: str
    model: str | None
    content_segments: list[str | ToolWidgetResult]


ChatTurnEvent = (
    ReasoningDeltaEvent
    | ContentDeltaEvent
    | ToolCallRequestedEvent
    | WidgetReadyEvent
    | CapReachedEvent
    | MessageDoneEvent
)


class ChatService:
    """Orchestrates a single chat turn: load history, run the bounded
    tool-execution loop against the LLM (delegated to `ToolCallExecutor`),
    persist the updated history.
    """

    def __init__(
        self,
        conversation_cache: ConversationCacheRepositoryInterface,
        openrouter_client: OpenRouterClientInterface,
        tool_registry: dict[str, ToolDefinition],
    ) -> None:
        self._conversation_cache = conversation_cache
        self._tool_executor = ToolCallExecutor(openrouter_client, tool_registry)

    async def send_message(
        self,
        conversation_id: str | None,
        user_message: str,
        tools: list[dict] | None = None,
    ) -> AsyncIterator[ChatTurnEvent]:
        """Streams reasoning/content deltas as they arrive from the tool
        loop, then persists the finished conversation and yields the
        terminal event(s).
        """
        resolved_conversation_id = conversation_id or str(uuid.uuid4())
        history = await self._conversation_cache.get_history(resolved_conversation_id)
        history.append(Message(role="user", content=user_message))

        completion_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        completion_messages.extend({"role": m.role, "content": m.content} for m in history)

        final_result: ChatCompletionResult | ToolLoopCapReached | None = None
        final_content_segments: list[str | ToolWidgetResult] = []
        try:
            async for event in self._tool_executor.run(
                completion_messages, tools if tools is not None else DEFAULT_TOOL_SCHEMAS
            ):
                if isinstance(event, TurnResolvedEvent):
                    final_result = event.result
                    final_content_segments = event.content_segments
                else:
                    yield event
        except OpenRouterRequestFailed as exc:
            raise ChatServiceUnavailable(str(exc)) from exc

        if final_result is None:
            raise ChatServiceUnavailable("Tool-execution loop ended without a result")

        reply_content = _reply_content(final_result)
        model = final_result.model if isinstance(final_result, ChatCompletionResult) else None

        if isinstance(final_result, ToolLoopCapReached):
            yield CapReachedEvent(
                content=final_result.partial_content, clarification=final_result.clarification
            )
            message_parts_segments: list[str | ToolWidgetResult] = [reply_content]
        else:
            message_parts_segments = final_content_segments

        history.append(Message(role="assistant", content=reply_content))
        await self._conversation_cache.save_history(
            resolved_conversation_id, history, ttl_seconds=CONVERSATION_HISTORY_TTL_SECONDS
        )
        yield MessageDoneEvent(
            conversation_id=resolved_conversation_id,
            content=reply_content,
            model=model,
            content_segments=message_parts_segments,
        )


def _reply_content(result: ChatCompletionResult | ToolLoopCapReached) -> str:
    """On a normal completion, the assistant's final content. On a
    cap-trip, the best-effort partial content plus the clarification ask --
    always shown to the user, never silently discarded and never replaced by
    a raw error.
    """
    if isinstance(result, ToolLoopCapReached):
        return f"{result.partial_content}\n\n{result.clarification}".strip()
    return result.content
