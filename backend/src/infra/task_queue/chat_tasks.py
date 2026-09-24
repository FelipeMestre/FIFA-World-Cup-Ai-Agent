"""Arq task that runs one chat turn's generation independent of any HTTP
connection -- enqueued by the chat endpoint instead of generating inline, so
a client navigating away or closing its tab never interrupts an in-flight
reply. Aborting the request used to kill this same work server-side before
it could persist (FastAPI's `StreamingResponse` cancels its generator task
the moment the client disconnects); running it as a background job removes
that coupling entirely -- the job finishes and persists regardless of who,
if anyone, is watching.

Progress is published to a per-conversation Redis Stream instead of yielded
to an SSE response, so any number of watchers can attach or detach without
affecting the run itself. `chat:turn-in-progress:{conversation_id}` is the
signal both the sidebar spinner and the one-turn-per-conversation guard
read; it is always cleared in `finally`, independent of Postgres session
state -- clearing a Redis key has no dependency on whether the session
needs rolling back first (that rule only applies to a *second* write on the
*same* aborted session).

This task assumes its caller (the conversation live socket, see `live_router.py`)
has already, synchronously and in this order: run `ChatService.start_turn`
(ownership check + get-or-create), reserved the turn by setting
`turn_in_progress_key` with `SET NX` (the actual one-turn-per-conversation
guard -- a duplicate send is rejected on that socket, before it ever
reaches this task), and persisted the user's own message via
`ChatService.persist_user_message`. The flag's value is the stream cursor
captured at reservation: the last id already in `chat:turn-stream:{id}`,
or `0-0` when the stream is empty. Watchers read strictly after that id,
so an earlier turn's entries can stay in the same key. This task never
re-persists the user's message, never re-attempts the `NX` reservation,
and never overwrites that cursor -- it only refreshes the flag's TTL to a
full window from when generation actually starts (the router's own TTL may
have partly ticked down while queued) and is responsible for clearing it.

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
import re
from dataclasses import dataclass
from typing import Literal, get_args
from uuid import UUID

from src.domain.chat.exceptions.chat_exceptions import ChatServiceUnavailable
from src.domain.chat.services.chat_service import (
    ChatService,
    ChatTurnEvent,
    chat_turn_event_payload,
)
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
from src.infra.task_queue.session_scope import session_scope

logger = logging.getLogger(__name__)

# Matches the job's own 5-minute Arq timeout (see worker.py) -- the flag
# should never outlive the job that set it, even if the process is killed
# hard enough to skip the `finally` block entirely.
TURN_IN_PROGRESS_TTL_SECONDS = 300

# How long a finished (or failed) turn's stream stays reattachable after its
# terminal entry lands. Only matters for "briefly away, came back" -- a
# reload past this window just reads the persisted `chat_message` instead.
TURN_STREAM_TTL_SECONDS = 900

# Approximate cap on a per-user event stream's length (`XADD ... MAXLEN ~`).
# Unlike the per-conversation turn stream above, this stream is long-lived
# across a user's whole session rather than scoped to one finished turn, so
# a TTL doesn't fit -- it is trimmed by length instead, to bound Redis
# memory without needing an expiry concept for an ever-growing log.
USER_EVENTS_STREAM_MAXLEN = 1000

# The fixed set of icons `categorize_conversation_task` is allowed to assign
# -- a `Literal` (for typing) with a `frozenset` view derived from it (for
# membership checks), so the prompt and the response validation both read
# from this one source of truth instead of duplicating the list.
CategoryIcon = Literal[
    "general",
    "player",
    "team",
    "match",
    "tactics",
    "transfer",
    "injury",
    "stats",
    "history",
]
CATEGORY_ICONS: frozenset[str] = frozenset(get_args(CategoryIcon))


def turn_stream_key(conversation_id: str) -> str:
    return f"chat:turn-stream:{conversation_id}"


def turn_in_progress_key(conversation_id: str) -> str:
    return f"chat:turn-in-progress:{conversation_id}"


def user_events_key(user_id: int) -> str:
    """A long-lived, per-user Redis stream (unlike `turn_stream_key`, which
    is per-conversation and TTL'd to one turn) that every device signed in
    as this user can attach to for account-wide events -- currently just
    `ConversationCategorizedEvent`, published by `categorize_conversation_task`.
    """
    return f"user:events:{user_id}"


# Exclusive start of an empty stream. `XREAD` after this id returns every
# entry. Also the cursor stored on the in-progress flag when a turn is
# reserved and the stream has no entries yet.
STREAM_CURSOR_ORIGIN = "0-0"

_STREAM_CURSOR_RE = re.compile(r"^\d+-\d+$")


def is_stream_cursor(value: str) -> bool:
    return _STREAM_CURSOR_RE.fullmatch(value) is not None


def _cursor_parts(cursor: str) -> tuple[int, int]:
    millis, sequence = cursor.split("-", 1)
    return int(millis), int(sequence)


def stream_cursor_precedes(left: str, right: str) -> bool:
    """True when `left` is strictly earlier than `right` in stream order."""
    return _cursor_parts(left) < _cursor_parts(right)


async def last_stream_cursor(conversation_id: str) -> str:
    """The id a new turn must read after. `0-0` when the stream is empty."""
    entries = await redis_client.xrevrange(turn_stream_key(conversation_id), count=1)
    if not entries:
        return STREAM_CURSOR_ORIGIN
    return entries[0][0]


async def stream_cursor_has_gap(conversation_id: str, cursor: str) -> bool:
    """True when entries between `cursor` and the first retained id are gone.

    `XREAD` after a missing id still returns every later entry. That tail is
    not a resume of what the client has: the ids in between were trimmed or
    the key was replaced. An empty stream is not a gap -- the turn may not
    have published yet.
    """
    if cursor == STREAM_CURSOR_ORIGIN:
        return False
    entries = await redis_client.xrange(turn_stream_key(conversation_id), count=1)
    if not entries:
        return False
    return stream_cursor_precedes(cursor, entries[0][0])


def serialize_user_message_event(
    conversation_id: str, message_id: int, content: str, title: str
) -> dict[str, str]:
    """Stream entry every connected client reads when a turn is accepted.

    Written by the live socket before the reply job starts, so a second
    device blocked on `XREAD` sees the user message without refreshing.
    """
    payload = json.dumps(
        {
            "conversation_id": conversation_id,
            "message_id": message_id,
            "content": content,
            "title": title,
        }
    )
    return {"event_type": "UserMessageEvent", "payload": payload}


def serialize_chat_turn_event(event: ChatTurnEvent) -> dict[str, str]:
    """Redis stream fields for one `ChatTurnEvent`. Field mapping lives in
    `chat_turn_event_payload`; this only JSON-encodes it, because `XADD`
    values must be strings.
    """
    event_type, payload = chat_turn_event_payload(event)
    return {"event_type": event_type, "payload": json.dumps(payload)}


@dataclass(frozen=True)
class ConversationCategorizedEvent:
    """Published to `user_events_key(user_id)` once `categorize_conversation_task`
    resolves a title + icon for a newly created conversation. Deliberately
    NOT part of the `ChatTurnEvent` union in `chat_service.py`: that union is
    the per-conversation turn state machine's own events, published to a
    different (per-conversation) stream, while this event is produced by
    this job for the per-user stream instead -- it just happens to live in
    this module because that is what produces it.
    """

    conversation_id: str
    title: str
    icon: str


def serialize_conversation_categorized_event(
    event: ConversationCategorizedEvent,
) -> dict[str, str]:
    """Redis stream fields for one `ConversationCategorizedEvent`. Carries
    its own `event_type` (rather than reusing `chat_turn_event_payload`'s
    dataclass-name convention) so a future consumer reading the merged
    per-conversation + per-user streams can discriminate between the two
    kinds of entries.
    """
    payload = json.dumps(
        {
            "conversation_id": event.conversation_id,
            "title": event.title,
            "icon": event.icon,
        }
    )
    return {"event_type": "ConversationCategorizedEvent", "payload": payload}


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
    event stream (`user_events_key`) so every connected device picks it up.
    A later task adds the SSE endpoint that reads that stream.

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
