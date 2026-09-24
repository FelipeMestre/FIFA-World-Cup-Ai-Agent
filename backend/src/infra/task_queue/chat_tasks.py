"""Arq tasks that run chat-related work independent of any HTTP connection --
enqueued by the chat endpoints instead of generating inline, so a client
navigating away or closing its tab never interrupts an in-flight reply.
Aborting the request used to kill this same work server-side before it could
persist (FastAPI's `StreamingResponse` cancels its generator task the moment
the client disconnects); running it as a background job removes that
coupling entirely -- the job finishes and persists regardless of who, if
anyone, is watching.

Progress is published to Redis Streams instead of yielded to an SSE
response, so any number of watchers can attach or detach without affecting
the run itself. The stream key builders, cursor helpers, and event
(de)serializers both jobs below rely on live in `chat_streams.py` (split out
purely to keep each file under this repo's 400-line-per-file cap).

`generate_chat_reply_task` assumes its caller (`POST /conversations/{id}/messages`
in `conversation_router.py`) has already, synchronously and in this order:
run `ChatService.start_turn` (ownership check + get-or-create), reserved the
turn by setting `turn_in_progress_key` with `SET NX` (the actual
one-turn-per-conversation guard -- a duplicate send is rejected there,
before it ever reaches this task), and persisted the user's own message via
`ChatService.persist_user_message`. The flag's value is the stream cursor
captured at reservation: the last id already in `chat:turn-stream:{id}`, or
`0-0` when the stream is empty. Watchers read strictly after that id, so an
earlier turn's entries can stay in the same key. This task never re-persists
the user's message, never re-attempts the `NX` reservation, and never
overwrites that cursor -- it only refreshes the flag's TTL to a full window
from when generation actually starts (the router's own TTL may have partly
ticked down while queued) and is responsible for clearing it.

A turn that fails outright (no reply produced at all -- `ChatServiceUnavailable`
or any other exception) also records a `chat_turn_failure` row against
`user_message_id`, in its own independent session (never the outer
`session_scope()` one, which may be left in an aborted transaction state by
whatever just failed). This is distinct from `PersistenceFailedEvent`, which
means a reply *was* generated and shown but only failed to save -- that path
already ends in a normal `MessageDoneEvent` and never touches this table.
"""

import json
import logging
from uuid import UUID

from src.domain.chat.exceptions.chat_exceptions import ChatServiceUnavailable
from src.domain.chat.services.chat_service import ChatService
from src.domain.chat.tools.registry import build_tool_registry
from src.infra.openrouter.client import get_openrouter_client
from src.infra.postgres.config import SessionFactory
from src.infra.postgres.repositories.chat_message_repository import get_chat_message_repository
from src.infra.postgres.repositories.chat_turn_failure_repository import (
    get_chat_turn_failure_repository,
)
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
from src.infra.task_queue.chat_streams import (
    CATEGORY_ICONS,
    TURN_IN_PROGRESS_TTL_SECONDS,
    TURN_STREAM_TTL_SECONDS,
    USER_EVENTS_STREAM_MAXLEN,
    ConversationCategorizedEvent,
    serialize_chat_turn_event,
    serialize_conversation_categorized_event,
    turn_in_progress_key,
    turn_stream_key,
    user_events_key,
)
from src.infra.task_queue.session_scope import session_scope

logger = logging.getLogger(__name__)


async def _publish_error(stream_key: str, event_type: str, detail: str) -> None:
    payload = json.dumps({"detail": detail})
    await redis_client.xadd(stream_key, {"event_type": event_type, "payload": payload})


async def _record_turn_failure(conversation_id: str, user_message_id: int, detail: str) -> None:
    # Its own independent session, same rationale as `send_message`'s
    # assistant-reply persistence: the outer `session_scope()` session may
    # be left in an aborted-transaction state by whatever just failed, and
    # this write must not depend on that.
    try:
        async with SessionFactory() as session:
            await get_chat_turn_failure_repository(session).record_failure(
                UUID(conversation_id), user_message_id, detail
            )
    except Exception:
        logger.exception(
            "Failed to record chat_turn_failure for conversation %s, message %s",
            conversation_id,
            user_message_id,
        )


async def generate_chat_reply_task(
    ctx: dict, conversation_id: str, user_id: int, user_message: str, user_message_id: int
) -> None:
    stream_key = turn_stream_key(conversation_id)
    progress_key = turn_in_progress_key(conversation_id)

    # The router already reserved this turn with `SET NX` before enqueueing.
    # Refresh the TTL only -- `SET` would overwrite the stream cursor stored
    # as the flag's value. The stream itself stays: watchers skip earlier
    # turns by reading after that cursor.
    await redis_client.expire(progress_key, TURN_IN_PROGRESS_TTL_SECONDS)

    try:
        async with session_scope() as session:
            chat_service = ChatService(
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
            try:
                async for event in chat_service.send_message(
                    conversation_id=UUID(conversation_id),
                    user_id=user_id,
                    user_message=user_message,
                ):
                    await redis_client.xadd(stream_key, serialize_chat_turn_event(event))
            except ChatServiceUnavailable as exc:
                # Non-recoverable-turn signal, published to the stream for
                # any watcher instead of raised into a live SSE response.
                await _publish_error(stream_key, "ChatServiceUnavailable", str(exc))
                raise
    except BaseException as exc:
        # `except Exception` alone would miss `asyncio.CancelledError` --
        # arq enforces its job timeout via `asyncio.wait_for`, which raises
        # exactly that on timeout, and it has been a `BaseException`, not an
        # `Exception`, since Python 3.8. Missing it here means a timed-out
        # generation would skip this branch (and the flag would only clear
        # via TURN_IN_PROGRESS_TTL_SECONDS expiring, not immediately) -- see
        # tasks.py's docstring for the prior incident this same gap caused
        # elsewhere in this codebase.
        if not isinstance(exc, ChatServiceUnavailable):
            logger.exception("Chat reply generation failed for conversation %s", conversation_id)
            await _publish_error(
                stream_key, exc.__class__.__name__, str(exc) or exc.__class__.__name__
            )
        # No reply was produced at all -- distinct from `PersistenceFailedEvent`,
        # which means a reply *was* generated and shown, just failed to save.
        await _record_turn_failure(
            conversation_id, user_message_id, str(exc) or exc.__class__.__name__
        )
        raise
    finally:
        # Always runs, success or failure, independent of the Postgres
        # session entirely -- this is a Redis op, nothing to roll back.
        await redis_client.delete(progress_key)
        await redis_client.expire(stream_key, TURN_STREAM_TTL_SECONDS)


_CATEGORIZATION_SYSTEM_PROMPT = (
    "You classify the first message of a brand-new conversation in a "
    "football (soccer) World Cup scouting AI app. Reply with STRICT JSON "
    "only -- no markdown, no code fences, no commentary before or after -- "
    'in exactly this shape: {"title": "<short descriptive title, max 50 '
    'characters>", "icon": "<one of: ' + ", ".join(sorted(CATEGORY_ICONS)) + '>"}'
)


def _categorization_messages(first_message: str) -> list[dict]:
    return [
        {"role": "system", "content": _CATEGORIZATION_SYSTEM_PROMPT},
        {"role": "user", "content": first_message},
    ]


async def categorize_conversation_task(
    ctx: dict, conversation_id: str, user_id: int, first_message: str
) -> None:
    """Runs once, right after a conversation's first message is accepted
    (see `ChatService.start_turn`'s `created`-only enqueue), to generate a
    short title + a fixed-enum icon from one cheap, non-streamed-to-the-user
    LLM call, persist the result, and publish it to the user's own long-lived
    event stream (`user_events_key`) so every connected device picks it up
    via the SSE endpoint in `conversation_router.py`.

    Calls `get_openrouter_client().create_chat_completion` directly (no
    `ToolCallExecutor` -- this is a single-shot classification, not a
    conversation with tools) and aggregates the streamed `delta_content`
    into one string itself, since the client has no non-streaming mode.

    Fire-and-forget and best-effort. Enqueued at most once per conversation
    (on creation), so there is no double-start race to guard against the
    way `generate_chat_reply_task` guards concurrent turns, and no
    `chat_turn_failure`-style row to record on failure: an LLM formatting
    miss, or any other error, just leaves the conversation with its default
    title and no icon, which is an acceptable non-fatal outcome for a
    cosmetic feature. Never retried.
    """
    try:
        content_parts: list[str] = []
        async for chunk in get_openrouter_client().create_chat_completion(
            _categorization_messages(first_message)
        ):
            if chunk.delta_content:
                content_parts.append(chunk.delta_content)

        try:
            parsed = json.loads("".join(content_parts))
        except json.JSONDecodeError:
            parsed = None

        title = parsed.get("title") if isinstance(parsed, dict) else None
        icon = parsed.get("icon") if isinstance(parsed, dict) else None
        if (
            not isinstance(title, str)
            or not title.strip()
            or not isinstance(icon, str)
            or icon not in CATEGORY_ICONS
        ):
            # Expected-possible LLM-formatting miss, not a bug -- log and
            # walk away. The conversation keeps its default title/no icon.
            logger.warning(
                "categorize_conversation_task got an unusable response for conversation %s: %r",
                conversation_id,
                parsed,
            )
            return
        title = title.strip()

        async with session_scope() as session:
            await get_conversation_repository(session).update_category(
                UUID(conversation_id), title, icon
            )
            await session.commit()

        await redis_client.xadd(
            user_events_key(user_id),
            serialize_conversation_categorized_event(
                ConversationCategorizedEvent(
                    conversation_id=conversation_id, title=title, icon=icon
                )
            ),
            maxlen=USER_EVENTS_STREAM_MAXLEN,
        )
    except Exception:
        logger.exception("categorize_conversation_task failed for conversation %s", conversation_id)
