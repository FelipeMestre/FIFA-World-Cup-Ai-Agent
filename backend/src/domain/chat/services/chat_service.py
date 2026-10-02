import logging
from collections.abc import AsyncIterator
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.chat.config import chat_history_settings
from src.domain.chat.exceptions.chat_exceptions import ChatServiceUnavailable
from src.domain.chat.model.chat_message import ChatMessage
from src.domain.chat.model.conversation import Conversation
from src.domain.chat.model.message import Message
from src.domain.chat.services.chat_history_rebuild_service import ChatHistoryRebuildService
from src.domain.chat.services.chat_turn_events import (
    CapReachedEvent,
    ChatTurnEvent,
    MessageDoneEvent,
    PersistenceFailedEvent,
)
from src.domain.chat.services.tool_call_executor import (
    ToolCallExecutor,
    ToolWidgetResult,
    TurnResolvedEvent,
)
from src.domain.chat.tools.registry import ALL_TOOL_SCHEMAS, ToolDefinition
from src.infra.openrouter.exceptions import OpenRouterRequestFailed
from src.infra.openrouter.interfaces.openrouter_client_interface import OpenRouterClientInterface
from src.infra.openrouter.schemas import ChatCompletionResult, ToolLoopCapReached
from src.infra.postgres.config import SessionFactory
from src.infra.postgres.interfaces.chat_message_repository_interface import (
    ChatMessageRepositoryInterface,
)
from src.infra.postgres.interfaces.conversation_repository_interface import (
    ConversationRepositoryInterface,
)
from src.infra.postgres.interfaces.match_repository_interface import MatchRepositoryInterface
from src.infra.postgres.interfaces.national_team_repository_interface import (
    NationalTeamRepositoryInterface,
)
from src.infra.postgres.repositories.chat_message_repository import get_chat_message_repository
from src.infra.postgres.repositories.conversation_repository import get_conversation_repository
from src.infra.redis.config import redis_client
from src.infra.redis.interfaces.conversation_cache_repository_interface import (
    ConversationCacheRepositoryInterface,
)
from src.infra.task_queue.chat_streams import (
    USER_EVENTS_STREAM_MAXLEN,
    ConversationCreatedEvent,
    serialize_conversation_created_event,
    user_events_key,
)
from src.infra.task_queue.pool import enqueue_categorize_conversation
from src.infra.tokens.repositories.tiktoken_token_counter import get_token_counter

logger = logging.getLogger(__name__)

_TITLE_MAX_LENGTH = 40

SYSTEM_PROMPT = (
    "You are a Football AI Scout Assistant. Based mostly on data from the FIFA World Cup 2026, but also other sources. "
    "Have a professional language and tone when answering messages"
    "You answer questions about teams, matches, and players using the data "
    "available in this application."
    "Always prioritize using tools to answer questions. If the tools doen't answer the question, say so and ask the user to provide more information."
    "If the tools doesn't answer the user's request of information, don't make up a response that might involve football data"
    "If a name seems to be mistaken, search first, and then, if data doesn't appear, try a corrected spelling or another alternative names"
    "If there are several alternativas for a name, like Luis Suarez, ask the user to provide more information to narrow down the search"
    "Don't use emojis in your answers."
)

CONVERSATION_HISTORY_TTL_SECONDS = 60 * 60 * 24  # 24h

DEFAULT_TOOL_SCHEMAS: list[dict] = ALL_TOOL_SCHEMAS


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
        match_repo: MatchRepositoryInterface,
        national_team_repo: NationalTeamRepositoryInterface,
        session: AsyncSession,
        history_rebuild_service: ChatHistoryRebuildService | None = None,
    ) -> None:
        self._conversation_cache = conversation_cache
        self._tool_executor = ToolCallExecutor(openrouter_client, tool_registry)
        self._conversation_repo = conversation_repo
        self._chat_message_repo = chat_message_repo
        self._match_repo = match_repo
        self._national_team_repo = national_team_repo
        self._session = session
        self._history_rebuild_service = history_rebuild_service or ChatHistoryRebuildService(
            chat_message_repo, get_token_counter(), chat_history_settings.TOKEN_BUDGET
        )

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
        # `created` is True only for a brand-new conversation row -- used
        # below to enqueue the categorization job exactly once per
        # conversation, on its first message.
        conversation, created = await self._conversation_repo.get_or_create(
            conversation_id, user_id, default_title=default_title
        )
        # Commit *here*, before returning to the router -- not deferred to
        # `send_message`'s eventual persistence step. FastAPI closes (and
        # therefore rolls back) request-scoped `Depends(get_db)` sessions as
        # soon as this endpoint function *returns*, which for a
        # `StreamingResponse` happens well before the response's async
        # generator actually runs. An uncommitted `get_or_create` here would
        # silently vanish by the time `send_message` tries to insert against
        # it (see `send_message`'s docstring for the other half of this).
        await self._session.commit()
        if created:
            # After the commit, deliberately -- enqueueing against a row
            # that might still roll back would let the job run (or race)
            # against a conversation that was never actually persisted.
            await enqueue_categorize_conversation(str(conversation_id), user_id, first_message)
            # Published so a device with no conversation open yet -- e.g.
            # sitting on the empty sidebar -- learns a new conversation
            # exists at all, via `GET /users/events` (`user_events_router.py`).
            await redis_client.xadd(
                user_events_key(user_id),
                serialize_conversation_created_event(
                    ConversationCreatedEvent(
                        conversation_id=str(conversation_id),
                        title=default_title,
                        created_at=conversation.created_at.isoformat(),
                    )
                ),
                maxlen=USER_EVENTS_STREAM_MAXLEN,
            )
        return conversation

    async def persist_user_message(
        self, conversation_id: UUID, content: str, metadata: dict | None = None
    ) -> ChatMessage:
        """Persists the user's own message synchronously, independent of
        whether the reply is ever generated -- called by the router right
        before enqueueing `generate_chat_reply_task`, so the user's message
        survives even if the job never runs. Uses `self._session` (the
        request-scoped session) and commits immediately, same pattern as
        `start_turn` -- this runs and finishes before the endpoint returns,
        unlike `send_message`'s own persistence step below, which must open
        its own independent session (see that docstring).

        Returns the persisted message so the router can pass its `id` on to
        `generate_chat_reply_task` -- the only thing a `chat_turn_failure`
        row can be recorded against on a failed turn.
        """
        message = await self._chat_message_repo.append_message(
            conversation_id, role="user", content=content, metadata=metadata
        )
        await self._session.commit()
        return message

    async def send_message(
        self,
        conversation_id: UUID,
        user_id: int,
        user_message: str,
        tools: list[dict] | None = None,
        context: dict | None = None,
    ) -> AsyncIterator[ChatTurnEvent]:
        """Streams reasoning/content deltas as they arrive from the tool
        loop, then persists the assistant's reply and yields the terminal
        event(s). Assumes `start_turn` has already been awaited, and that
        the user's own message has already been persisted via
        `persist_user_message` -- this method only ever appends the
        assistant's reply, never the user's turn.

        `context` is `MessageContextDto.model_dump()` (currently just
        `match_id`) from the match-selector chip. When it resolves, this
        injects a **directive imperative instruction** naming the exact tool
        and arguments to call -- never a passive "take this into account"
        fact statement. An earlier (reverted) player/team-selector feature
        used passive phrasing and the model sometimes skipped the matching
        tool call even with the data named right there; the user confirmed
        for this feature that a pinned match must force `get_match_analysis`
        use, so the injected message is phrased as a command instead.
        """
        resolved_conversation_id = str(conversation_id)
        history = await self._load_prompt_history(conversation_id)
        history.append(Message(role="user", content=user_message))

        completion_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        match_directive = await self._build_match_directive(context)
        if match_directive is not None:
            completion_messages.append({"role": "system", "content": match_directive})
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
            # Deliberately NOT using `self._chat_message_repo`/
            # `self._conversation_repo`/`self._session` here -- those are
            # bound to the request-scoped `Depends(get_db)` session, which
            # FastAPI has already closed (rolled back) by the time this
            # generator runs, for the same `StreamingResponse`-vs-`yield`-
            # dependency-cleanup-ordering reason documented on `start_turn`.
            # This block opens its own short-lived session so the write
            # survives independently of the request's dependency lifecycle.
            async with SessionFactory() as turn_session:
                chat_message_repo = get_chat_message_repository(turn_session)
                conversation_repo = get_conversation_repository(turn_session)
                widgets = [
                    (w.tool_name, w.widget_type, w.data)
                    for w in message_parts_segments
                    if isinstance(w, ToolWidgetResult)
                ]
                await chat_message_repo.append_message(
                    conversation_id, role="assistant", content=reply_content, widgets=widgets
                )
                await conversation_repo.touch(conversation_id)
                await turn_session.commit()
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

    async def _load_prompt_history(self, conversation_id: UUID) -> list[Message]:
        """Redis first; on a miss (never cached, 24h expiry, flush, failed
        turn) rebuild the text-only history from Postgres and write it back
        so later turns reuse the same stable prompt prefix. The rebuild
        excludes the current user message (already persisted, appended by
        the caller). Never raises: a failed rebuild degrades to an empty
        history (the pre-rebuild behavior) rather than failing the turn.
        """
        resolved_conversation_id = str(conversation_id)
        history = await self._conversation_cache.get_history(resolved_conversation_id)
        if history:
            return history
        try:
            history = await self._history_rebuild_service.rebuild(conversation_id)
        except Exception:
            logger.exception(
                "Failed to rebuild chat history from Postgres for conversation %s", conversation_id
            )
            return []
        if history:
            try:
                await self._conversation_cache.save_history(
                    resolved_conversation_id, history, ttl_seconds=CONVERSATION_HISTORY_TTL_SECONDS
                )
            except Exception:
                logger.exception(
                    "Failed to cache rebuilt chat history for conversation %s (non-fatal)",
                    conversation_id,
                )
        return history

    async def _build_match_directive(self, context: dict | None) -> str | None:
        """Resolves `context["match_id"]` (from `MessageContextDto`) into the
        directive instruction injected in `send_message`, or `None` on any
        missing/unset/unresolved id -- silent best-effort, same philosophy as
        the router's own `_resolve_message_metadata`. Never raises.
        """
        if not context:
            return None
        match_id = context.get("match_id")
        if match_id is None:
            return None

        match = await self._match_repo.get(match_id)
        if match is None:
            return None
        home_team = await self._national_team_repo.get(match.home_team_id)
        away_team = await self._national_team_repo.get(match.away_team_id)
        if home_team is None or away_team is None:
            return None

        date_iso = match.date.isoformat()
        return (
            f"The user selected this specific match via the match selector: "
            f"{home_team.name} vs {away_team.name} on {date_iso}.\n"
            f"You MUST call the get_match_analysis tool with "
            f'home_team_name="{home_team.name}", away_team_name="{away_team.name}", '
            f'date="{date_iso}" before answering anything about this match. '
            f"Do not answer from assumptions."
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
