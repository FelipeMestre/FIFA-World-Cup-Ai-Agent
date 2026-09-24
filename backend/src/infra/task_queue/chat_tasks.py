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

This task assumes its caller (`POST /chat/messages`, see `chat_router.py`)
has already, synchronously and in this order: run `ChatService.start_turn`
(ownership check + get-or-create), reserved the turn by setting
`turn_in_progress_key` with `SET NX` (the actual one-turn-per-conversation
guard -- a duplicate enqueue is rejected there with a 409, before it ever
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


def turn_stream_key(conversation_id: str) -> str:
    return f"chat:turn-stream:{conversation_id}"


def turn_in_progress_key(conversation_id: str) -> str:
    return f"chat:turn-in-progress:{conversation_id}"


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


def serialize_chat_turn_event(event: ChatTurnEvent) -> dict[str, str]:
    """Redis stream fields for one `ChatTurnEvent`. Field mapping lives in
    `chat_turn_event_payload`; this only JSON-encodes it, because `XADD`
    values must be strings.
    """
    event_type, payload = chat_turn_event_payload(event)
    return {"event_type": event_type, "payload": json.dumps(payload)}


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
