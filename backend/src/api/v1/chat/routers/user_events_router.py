"""Dedicated per-user realtime event stream -- the T6 fix for a browser
window sitting on the empty `/home` screen (or on a different conversation)
never learning that a new conversation was created, or that a background
categorization job just finished, anywhere in the account.

Sibling of `conversation_router.py`'s `GET /{conversation_id}/events`, but
deliberately simpler: single Redis key (`user_events_key`), single cursor,
no `conversation_id` path param and no ownership check -- there is nothing
to check ownership of, the stream is the caller's own by construction (it is
keyed by `user_id` straight off the JWT). See that router's `_conversation_events`
for the sibling loop this one intentionally does not share code with (kept
as two small, independently-readable loops rather than one shared generator
threading two different event vocabularies through one abstraction).
"""

import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Header, Request
from fastapi.responses import StreamingResponse

from src.api.v1.auth.services.dependencies import JwtDataDep
from src.api.v1.chat.sse import user_event_message
from src.infra.redis.config import redis_client
from src.infra.task_queue.chat_streams import (
    is_stream_cursor,
    last_user_events_cursor,
    user_events_key,
)

router = APIRouter(prefix="/users", tags=["users"])

# Same blocking window and keep-alive cadence as
# `conversation_router.py`'s turn-stream loop -- kept identical
# deliberately so the two SSE endpoints behave the same way to any
# reverse proxy or load balancer sitting in front of them, even though the
# loop bodies themselves are not shared code.
_READ_BLOCK_MS = 1_000
_KEEPALIVE_EMPTY_POLLS = 15


async def _user_events(request: Request, user_key: str, cursor: str) -> AsyncIterator[str]:
    empty_polls = 0
    while True:
        if await request.is_disconnected():
            return

        response = await redis_client.xread({user_key: cursor}, block=_READ_BLOCK_MS)
        if not response:
            empty_polls += 1
            if empty_polls >= _KEEPALIVE_EMPTY_POLLS:
                yield ": keep-alive\n\n"
                empty_polls = 0
            continue
        empty_polls = 0

        for _stream_name, entries in response:
            for entry_id, fields in entries:
                cursor = entry_id
                event_name, data = user_event_message(
                    entry_id, fields["event_type"], json.loads(fields["payload"])
                )
                yield f"id: {cursor}\nevent: {event_name}\ndata: {json.dumps(data)}\n\n"


@router.get(
    "/events",
    summary="Account-wide realtime event stream",
    description="Server-Sent Events stream of the authenticated user's own account-wide "
    "events -- `event: conversation_created` when any device on this account starts a new "
    "conversation, `event: conversation_updated` when a background categorization job "
    "resolves a title/icon for one. Not scoped to any single conversation: meant to be opened "
    "once, for as long as the sidebar is mounted, independent of which (if any) conversation "
    "is selected -- unlike `GET /conversations/{id}/events`, which only carries that one "
    "conversation's turn stream. Resumes from the `Last-Event-ID` header when present and "
    "valid; a fresh connection with no header starts at the stream's tail, not its full "
    "history.",
)
async def stream_user_events(
    request: Request,
    jwt_data: JwtDataDep,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    user_id = int(jwt_data["sub"])
    user_key = user_events_key(user_id)
    if last_event_id is not None and is_stream_cursor(last_event_id):
        cursor = last_event_id
    else:
        cursor = await last_user_events_cursor(user_id)

    return StreamingResponse(
        _user_events(request, user_key, cursor),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Reverse proxies like nginx buffer a response by default, which
            # would defeat SSE entirely -- this tells them not to. Has no
            # effect locally, but matters once this sits behind one.
            "X-Accel-Buffering": "no",
        },
    )
