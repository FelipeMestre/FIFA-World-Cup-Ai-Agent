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
read; it is set with `NX` (only if absent) so a stray duplicate enqueue
can't stomp on an already-running turn's flag, and always cleared in
`finally`, independent of Postgres session state -- clearing a Redis key
has no dependency on whether the session needs rolling back first (that
rule only applies to a *second* write on the *same* aborted session).

This task assumes `ChatService.start_turn` (ownership check + get-or-create)
has already run synchronously, before this job was enqueued -- same
contract `ChatService.send_message` already documents. Which caller enqueues
this job, and how the ownership check stays synchronous, is not decided
here; see odd/tasks/chat-memory.md.
"""

import json
import logging
from uuid import UUID

from src.domain.chat.exceptions.chat_exceptions import ChatServiceUnavailable
from src.domain.chat.services.chat_service import (
    CapReachedEvent,
    ChatService,
    ChatTurnEvent,
    ContentDeltaEvent,
    MessageDoneEvent,
    PersistenceFailedEvent,
    ReasoningDeltaEvent,
)
from src.domain.chat.services.tool_call_executor import (
    ToolCallRequestedEvent,
    ToolWidgetResult,
    WidgetReadyEvent,
)
from src.domain.chat.tools.registry import build_tool_registry
from src.infra.openrouter.client import get_openrouter_client
from src.infra.postgres.repositories.chat_message_repository import get_chat_message_repository
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


def _widget_result_to_dict(widget: ToolWidgetResult) -> dict:
    return {
        "tool_call_id": widget.tool_call_id,
        "tool_name": widget.tool_name,
        "widget_type": widget.widget_type,
        "data": widget.data,
    }


def _segment_to_dict(segment: str | ToolWidgetResult) -> dict:
    if isinstance(segment, str):
        return {"kind": "text", "content": segment}
    return {"kind": "widget", **_widget_result_to_dict(segment)}


def serialize_chat_turn_event(event: ChatTurnEvent) -> dict[str, str]:
    """Flattens one `ChatTurnEvent` into a JSON-safe, string-valued dict for
    `XADD` (Redis stream fields must be strings). `event_type` names the
    dataclass; `payload` is that event's own fields, JSON-encoded.

    Deliberately NOT the SSE wire DTO shape from `chat_dtos.py` -- this task
    lives in the infra layer and must not import the API layer's DTOs
    (backwards dependency). Whatever reads this stream back owns converting
    this into a DTO, symmetric with how `chat_router.py`'s `_to_dto` already
    converts a live `ChatTurnEvent` for the SSE path.
    """
    if isinstance(event, (ReasoningDeltaEvent, ContentDeltaEvent)):
        payload = {"content": event.content}
    elif isinstance(event, ToolCallRequestedEvent):
        payload = {"name": event.name}
    elif isinstance(event, WidgetReadyEvent):
        payload = {"widget": _widget_result_to_dict(event.widget)}
    elif isinstance(event, CapReachedEvent):
        payload = {"content": event.content, "clarification": event.clarification}
    elif isinstance(event, PersistenceFailedEvent):
        payload = {"detail": event.detail}
    elif isinstance(event, MessageDoneEvent):
        payload = {
            "conversation_id": event.conversation_id,
            "content": event.content,
            "model": event.model,
            "content_segments": [_segment_to_dict(s) for s in event.content_segments],
        }
    else:
        raise ValueError(f"Unhandled chat stream event: {event!r}")
    return {"event_type": type(event).__name__, "payload": json.dumps(payload)}


async def _publish_error(stream_key: str, event_type: str, detail: str) -> None:
    payload = json.dumps({"detail": detail})
    await redis_client.xadd(stream_key, {"event_type": event_type, "payload": payload})


async def generate_chat_reply_task(
    ctx: dict, conversation_id: str, user_id: int, user_message: str
) -> None:
    stream_key = turn_stream_key(conversation_id)
    progress_key = turn_in_progress_key(conversation_id)

    acquired = await redis_client.set(progress_key, "1", nx=True, ex=TURN_IN_PROGRESS_TTL_SECONDS)
    if not acquired:
        # A turn is already in progress for this conversation -- the
        # one-turn-per-conversation guard should have stopped this job from
        # ever being enqueued twice; this is a defensive no-op, not the
        # primary enforcement point.
        logger.warning(
            "generate_chat_reply_task skipped: a turn is already in progress for conversation %s",
            conversation_id,
        )
        return

    await redis_client.delete(stream_key)  # drop any stale entries from a prior turn

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
                # Mirrors chat_router.py's `_stream_chat_events`, which
                # catches this same exception and emits an `error` SSE
                # event for the live path -- same non-recoverable-turn
                # signal, just published for a watcher instead of streamed.
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
        raise
    finally:
        # Always runs, success or failure, independent of the Postgres
        # session entirely -- this is a Redis op, nothing to roll back.
        await redis_client.delete(progress_key)
        await redis_client.expire(stream_key, TURN_STREAM_TTL_SECONDS)
