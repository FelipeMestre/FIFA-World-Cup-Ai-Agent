import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.chat.exceptions.chat_exceptions import ChatServiceUnavailable
from src.domain.chat.model.conversation import Conversation
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
from src.infra.postgres.interfaces.chat_message_repository_interface import (
    ChatMessageRepositoryInterface,
)
from src.infra.postgres.interfaces.conversation_repository_interface import (
    ConversationRepositoryInterface,
)
from src.infra.redis.interfaces.conversation_cache_repository_interface import (
    ConversationCacheRepositoryInterface,
)

logger = logging.getLogger(__name__)

_TITLE_MAX_LENGTH = 40

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
class PersistenceFailedEvent:
    """Non-fatal: the Postgres durable write for this turn (or the
    `conversation.touch()` alongside it) failed. Unlike `ChatServiceUnavailable`
    (which aborts the stream before any content has been sent), this is
    raised *after* the reply has already streamed to the user via
    `content_delta`/`widget_ready` events, so the turn always still finishes
    with a `MessageDoneEvent` -- this event only warns the frontend that the
    just-shown message may not survive a reload. The Redis cache write is
    handled separately and never surfaces here: it is a rebuildable
    read-through cache and its own failure is swallowed silently.
    """

    detail: str


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
    | PersistenceFailedEvent
    | MessageDoneEvent
)


class ChatService:
    """Orchestrates a single chat turn: load history, run the bounded
    tool-execution loop against the LLM (delegated to `ToolCallExecutor`),
    persist the updated history to Postgres (source of truth) and Redis
    (read-through cache).
    """

    def __init__(
        self,
        conversation_cache: ConversationCacheRepositoryInterface,
        openrouter_client: OpenRouterClientInterface,
        tool_registry: dict[str, ToolDefinition],
        conversation_repo: ConversationRepositoryInterface,
        chat_message_repo: ChatMessageRepositoryInterface,
        session: AsyncSession,
    ) -> None:
        self._conversation_cache = conversation_cache
        self._tool_executor = ToolCallExecutor(openrouter_client, tool_registry)
        self._conversation_repo = conversation_repo
        self._chat_message_repo = chat_message_repo
        self._session = session

    async def start_turn(
        self, conversation_id: UUID, user_id: int, first_message: str
    ) -> Conversation:
        """Must be called -- and awaited -- before any SSE streaming starts.
        Performs the ownership check up front so a `ConversationOwnershipError`
        can still become a clean HTTP 403: once `StreamingResponse` begins
        iterating `send_message`'s generator, headers are already committed
        to 200 and an exception can no longer change the status code.

        Lets `ConversationOwnershipError` propagate uncaught -- the router
        catches it.
        """
        default_title = first_message[:_TITLE_MAX_LENGTH].strip()
        if len(first_message) > _TITLE_MAX_LENGTH:
            default_title += "…"
        return await self._conversation_repo.get_or_create(
            conversation_id, user_id, default_title=default_title
        )

    async def send_message(
        self,
        conversation_id: UUID,
        user_id: int,
        user_message: str,
        tools: list[dict] | None = None,
    ) -> AsyncIterator[ChatTurnEvent]:
        """Streams reasoning/content deltas as they arrive from the tool
        loop, then persists the finished conversation and yields the
        terminal event(s). Assumes `start_turn` has already been awaited for
        this `conversation_id`/`user_id` pair.
        """
        resolved_conversation_id = str(conversation_id)
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

        try:
            await self._chat_message_repo.append_message(
                conversation_id, role="user", content=user_message
            )
            widgets = [
                (w.tool_name, w.widget_type, w.data)
                for w in message_parts_segments
                if isinstance(w, ToolWidgetResult)
            ]
            await self._chat_message_repo.append_message(
                conversation_id, role="assistant", content=reply_content, widgets=widgets
            )
            await self._conversation_repo.touch(conversation_id)
            await self._session.commit()
        except Exception:
            logger.exception(
                "Failed to persist chat turn to Postgres for conversation %s", conversation_id
            )
            # Postgres is the source of truth -- unlike the Redis write
            # below, this failure is NOT swallowed silently from the user's
            # perspective: surface it as a non-fatal SSE event so the
            # frontend can warn the user this message may not survive a
            # reload, but still finish the turn (the text was already
            # streamed via content_delta/widget_ready events; don't leave
            # the client hanging on a broken/truncated stream).
            yield PersistenceFailedEvent(
                detail="This message could not be saved. It may not be here after a reload."
            )

        history.append(Message(role="assistant", content=reply_content))
        try:
            await self._conversation_cache.save_history(
                resolved_conversation_id, history, ttl_seconds=CONVERSATION_HISTORY_TTL_SECONDS
            )
        except Exception:
            logger.exception(
                "Failed to write chat history to Redis cache for conversation %s "
                "(non-fatal, DB already has it)",
                conversation_id,
            )
            # Swallow -- Redis is a rebuildable read-through cache, per this
            # feature's already-agreed design; must never fail the request.

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
