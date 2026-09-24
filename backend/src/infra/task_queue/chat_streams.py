"""Redis Stream vocabulary shared by the chat Arq jobs (`chat_tasks.py`) and
every HTTP endpoint that publishes to or reads from those streams: stream key
builders, cursor helpers, and the (de)serialization of each event kind that
crosses a stream (`XADD` values must be strings, so every event is flattened
to an `event_type` + JSON `payload` pair of fields).

Split out of `chat_tasks.py` purely to keep both files under this repo's
400-line-per-file cap (`CLAUDE.md`) -- neither file owns a materially
different concept, this is one cohesive module divided for size. The two
Arq job bodies (`generate_chat_reply_task`, `categorize_conversation_task`)
stay in `chat_tasks.py`; everything else that module used to define -- key
builders, cursor helpers, event (de)serializers, and the constants they use
-- lives here instead, alongside the two read-side cursor helpers
(`resume_turn_cursor`, `last_user_events_cursor`) the SSE endpoint in
`conversation_router.py` needs.
"""

import json
import re
from dataclasses import dataclass
from typing import Literal, get_args

from src.domain.chat.services.chat_service import ChatTurnEvent, chat_turn_event_payload
from src.infra.redis.config import redis_client

# Matches `generate_chat_reply_task`'s own 5-minute Arq timeout (see
# worker.py) -- the flag should never outlive the job that set it, even if
# the process is killed hard enough to skip its `finally` block entirely.
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


async def last_user_events_cursor(user_id: int) -> str:
    """The id a fresh SSE connection with no `Last-Event-ID` must read after,
    on the per-user stream. Mirrors `last_stream_cursor`'s idle-conversation
    behavior, for the same reason: this stream spans a user's whole session,
    so a client connecting for the first time starts at the tail instead of
    replaying their entire categorization-event history.
    """
    entries = await redis_client.xrevrange(user_events_key(user_id), count=1)
    if not entries:
        return STREAM_CURSOR_ORIGIN
    return entries[0][0]


async def resume_turn_cursor(conversation_id: str) -> str:
    """Where a newly attached reader starts reading the turn stream.

    An in-progress turn replays from the cursor stored at reservation, which
    is before that turn's user message. An idle conversation starts at the
    end of the stream so history already loaded from Postgres is not replayed.
    """
    stored = await redis_client.get(turn_in_progress_key(conversation_id))
    if isinstance(stored, str) and is_stream_cursor(stored):
        return stored
    return await last_stream_cursor(conversation_id)


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

    Written by the send endpoint before the reply job starts, so a second
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
    that job for the per-user stream instead -- it just happens to live in
    this module because that is what every other event's (de)serializer
    lives in.
    """

    conversation_id: str
    title: str
    icon: str


def serialize_conversation_categorized_event(
    event: ConversationCategorizedEvent,
) -> dict[str, str]:
    """Redis stream fields for one `ConversationCategorizedEvent`. Carries
    its own `event_type` (rather than reusing `chat_turn_event_payload`'s
    dataclass-name convention) so the merged SSE endpoint reading both the
    per-conversation and per-user streams can discriminate between the two
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
