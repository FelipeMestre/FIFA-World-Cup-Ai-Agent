"""Integration tests for `GET /conversations/{id}/events`, the merged SSE
endpoint that replaces the old live WebSocket's receive side. Uses real
Postgres and Redis (no mocking, per AGENTS.md's testing anti-pattern table).

Testing a live blocking `StreamingResponse` generator needs a real HTTP
connection, not `httpx.ASGITransport` -- that transport fully drains the
ASGI app (buffering the whole response body) before `handle_async_request`
returns anything at all, which never happens against this endpoint's
deliberately-infinite generator. Same reasoning as the old
`test_conversation_live.py`'s `live_port` fixture (real WebSocket needs a
real socket): a real `uvicorn.Server` is started on a free port, and each
streaming test connects to it with a plain `httpx.AsyncClient` (no
transport override) so bytes are delivered incrementally as the server
writes them.

Entries are pre-seeded via direct `redis_client.xadd` calls BEFORE opening
the SSE connection, so the endpoint's initial catch-up read picks them up
immediately without needing real concurrency/background tasks. Each test
reads exactly the number of frames it expects via a bounded `aiter_lines()`
helper, then lets the `async with` block close the connection -- never
tries to fully drain the endpoint's otherwise-infinite generator.

An explicit `Last-Event-ID: "0-0|0-0"` (the stream origin for both halves)
is used to make delivery deterministic on the first connection in tests 1
and 2, instead of relying on the no-header default (which intentionally
starts at each stream's tail -- see `chat_streams.py`'s `resume_turn_cursor`
and `last_user_events_cursor` docstrings -- and would otherwise race against
the entries these tests just seeded).
"""

import asyncio
import json
import socket
from collections.abc import AsyncGenerator, AsyncIterator
from typing import Any
from uuid import uuid4

import pytest
import uvicorn
from httpx import AsyncClient
from sqlalchemy import text

from src.api.v1.auth.services.dependencies import parse_jwt_data
from src.domain.chat.services.chat_service import MessageDoneEvent
from src.infra.postgres.config import SessionFactory
from src.infra.postgres.repositories.conversation_repository import (
    _SqlAlchemyConversationRepository,
)
from src.infra.redis.config import redis_client
from src.infra.task_queue.chat_streams import (
    STREAM_CURSOR_ORIGIN,
    ConversationCategorizedEvent,
    serialize_chat_turn_event,
    serialize_conversation_categorized_event,
    turn_in_progress_key,
    turn_stream_key,
    user_events_key,
)
from src.main import app

_USER_ID = 990901
_OTHER_USER_ID = 990902
_ORIGIN_LAST_EVENT_ID = f"{STREAM_CURSOR_ORIGIN}|{STREAM_CURSOR_ORIGIN}"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
async def sse_port() -> AsyncGenerator[int]:
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    task = asyncio.create_task(server.serve())
    for _ in range(100):
        if server.started:
            break
        await asyncio.sleep(0.02)
    else:
        server.should_exit = True
        await task
        raise RuntimeError("SSE test server did not start")
    yield port
    server.should_exit = True
    await task


@pytest.fixture
async def sse_client(sse_port: int) -> AsyncGenerator[AsyncClient]:
    async with AsyncClient(base_url=f"http://127.0.0.1:{sse_port}/api/v1") as ac:
        yield ac


@pytest.fixture(autouse=True)
async def _seed_users() -> AsyncGenerator[None]:
    async with SessionFactory() as session:
        for user_id in (_USER_ID, _OTHER_USER_ID):
            # `name` is passed as its own bound parameter rather than derived
            # in SQL from a reused `:email` -- see the identical note in
            # `test_conversation_endpoints.py` for why (pre-existing asyncpg
            # `AmbiguousParameterError`, unrelated to this task).
            await session.execute(
                text(
                    'INSERT INTO "user" (id, email, name, password_hash, is_admin, created_at) '
                    "VALUES (:id, :email, :name, 'hash', false, now())"
                ),
                {
                    "id": user_id,
                    "email": f"conversation-events-test-{user_id}@example.test",
                    "name": f"conversation-events-test-{user_id}",
                },
            )
        await session.commit()
    yield
    async with SessionFactory() as cleanup_session:
        await cleanup_session.execute(
            text(
                "DELETE FROM chat_message WHERE conversation_id IN "
                "(SELECT id FROM conversation WHERE user_id IN (:a, :b))"
            ),
            {"a": _USER_ID, "b": _OTHER_USER_ID},
        )
        await cleanup_session.execute(
            text("DELETE FROM conversation WHERE user_id IN (:a, :b)"),
            {"a": _USER_ID, "b": _OTHER_USER_ID},
        )
        await cleanup_session.execute(
            text('DELETE FROM "user" WHERE id IN (:a, :b)'), {"a": _USER_ID, "b": _OTHER_USER_ID}
        )
        await cleanup_session.commit()


@pytest.fixture(autouse=True)
def _override_auth() -> AsyncGenerator[None]:
    def fake_jwt_data() -> dict[str, Any]:
        return {"sub": str(_USER_ID), "is_admin": False}

    app.dependency_overrides[parse_jwt_data] = fake_jwt_data
    yield
    app.dependency_overrides.clear()


async def _create_conversation(user_id: int, title: str) -> Any:
    async with SessionFactory() as session:
        repo = _SqlAlchemyConversationRepository(session)
        conversation, _created = await repo.get_or_create(uuid4(), user_id, title)
        await session.commit()
        return conversation


async def _cleanup_turn_state(conversation_id: str) -> None:
    await redis_client.delete(
        turn_in_progress_key(conversation_id), turn_stream_key(conversation_id)
    )


async def _cleanup_user_events(user_id: int) -> None:
    await redis_client.delete(user_events_key(user_id))


async def _read_frame(lines: AsyncIterator[str]) -> tuple[str, str, dict]:
    """Reads one SSE frame (`id:`, `event:`, `data:`, blank line) off an
    `httpx.Response.aiter_lines()` iterator and returns `(id, event, data)`
    with `data` parsed from JSON.
    """
    id_line = await anext(lines)
    event_line = await anext(lines)
    data_line = await anext(lines)
    blank_line = await anext(lines)
    assert id_line.startswith("id: "), id_line
    assert event_line.startswith("event: "), event_line
    assert data_line.startswith("data: "), data_line
    assert blank_line == ""
    return (
        id_line.removeprefix("id: "),
        event_line.removeprefix("event: "),
        json.loads(data_line.removeprefix("data: ")),
    )


@pytest.mark.asyncio
async def test_sse_delivers_a_pre_seeded_turn_stream_entry(sse_client: AsyncClient) -> None:
    conversation = await _create_conversation(_USER_ID, "Turn stream conversation")
    conversation_id = str(conversation.id)

    event = MessageDoneEvent(
        conversation_id=conversation_id,
        content="Hello from the turn stream",
        model="anthropic/claude-sonnet-4.5",
        content_segments=["Hello from the turn stream"],
    )
    await redis_client.xadd(turn_stream_key(conversation_id), serialize_chat_turn_event(event))

    async with sse_client.stream(
        "GET",
        f"/conversations/{conversation_id}/events",
        headers={"Authorization": "Bearer test-token", "Last-Event-ID": _ORIGIN_LAST_EVENT_ID},
    ) as response:
        assert response.status_code == 200
        lines = response.aiter_lines()
        entry_id, event_name, data = await asyncio.wait_for(_read_frame(lines), timeout=5)

    assert event_name == "turn"
    assert entry_id.split("|")[0] == data["cursor"]
    assert data["type"] == "message_done"
    assert data["conversation_id"] == conversation_id
    assert data["parts"] == [{"type": "text", "content": "Hello from the turn stream"}]

    await _cleanup_turn_state(conversation_id)


@pytest.mark.asyncio
async def test_sse_delivers_a_pre_seeded_user_stream_entry(sse_client: AsyncClient) -> None:
    conversation = await _create_conversation(_USER_ID, "Categorized conversation")
    conversation_id = str(conversation.id)

    await redis_client.xadd(
        user_events_key(_USER_ID),
        serialize_conversation_categorized_event(
            ConversationCategorizedEvent(
                conversation_id=conversation_id, title="Injury update: Player X", icon="injury"
            )
        ),
    )

    async with sse_client.stream(
        "GET",
        f"/conversations/{conversation_id}/events",
        headers={"Authorization": "Bearer test-token", "Last-Event-ID": _ORIGIN_LAST_EVENT_ID},
    ) as response:
        assert response.status_code == 200
        lines = response.aiter_lines()
        entry_id, event_name, data = await asyncio.wait_for(_read_frame(lines), timeout=5)

    assert event_name == "conversation_updated"
    assert data == {
        "type": "conversation_updated",
        "cursor": entry_id.split("|")[1],
        "conversation_id": conversation_id,
        "title": "Injury update: Player X",
        "icon": "injury",
    }

    await _cleanup_user_events(_USER_ID)


@pytest.mark.asyncio
async def test_sse_resume_from_last_event_id_does_not_redeliver_seen_entries(
    sse_client: AsyncClient,
) -> None:
    conversation = await _create_conversation(_USER_ID, "Resume conversation")
    conversation_id = str(conversation.id)

    await redis_client.xadd(
        turn_stream_key(conversation_id),
        serialize_chat_turn_event(
            MessageDoneEvent(
                conversation_id=conversation_id,
                content="First reply",
                model=None,
                content_segments=["First reply"],
            )
        ),
    )
    await redis_client.xadd(
        user_events_key(_USER_ID),
        serialize_conversation_categorized_event(
            ConversationCategorizedEvent(
                conversation_id=conversation_id, title="First title", icon="general"
            )
        ),
    )

    async with sse_client.stream(
        "GET",
        f"/conversations/{conversation_id}/events",
        headers={"Authorization": "Bearer test-token", "Last-Event-ID": _ORIGIN_LAST_EVENT_ID},
    ) as response:
        assert response.status_code == 200
        lines = response.aiter_lines()
        _first_id, first_event, _first_data = await asyncio.wait_for(_read_frame(lines), timeout=5)
        captured_id, second_event, _second_data = await asyncio.wait_for(
            _read_frame(lines), timeout=5
        )

    assert {first_event, second_event} == {"turn", "conversation_updated"}
    assert captured_id.count("|") == 1

    await redis_client.xadd(
        turn_stream_key(conversation_id),
        serialize_chat_turn_event(
            MessageDoneEvent(
                conversation_id=conversation_id,
                content="Second reply",
                model=None,
                content_segments=["Second reply"],
            )
        ),
    )
    await redis_client.xadd(
        user_events_key(_USER_ID),
        serialize_conversation_categorized_event(
            ConversationCategorizedEvent(
                conversation_id=conversation_id, title="Second title", icon="stats"
            )
        ),
    )

    async with sse_client.stream(
        "GET",
        f"/conversations/{conversation_id}/events",
        headers={"Authorization": "Bearer test-token", "Last-Event-ID": captured_id},
    ) as response:
        assert response.status_code == 200
        lines = response.aiter_lines()
        _resumed_first_id, resumed_first_event, resumed_first_data = await asyncio.wait_for(
            _read_frame(lines), timeout=5
        )
        _resumed_second_id, resumed_second_event, resumed_second_data = await asyncio.wait_for(
            _read_frame(lines), timeout=5
        )

    resumed = {
        resumed_first_event: resumed_first_data,
        resumed_second_event: resumed_second_data,
    }
    assert set(resumed) == {"turn", "conversation_updated"}
    assert resumed["turn"]["parts"] == [{"type": "text", "content": "Second reply"}]
    assert resumed["conversation_updated"]["title"] == "Second title"
    assert resumed["conversation_updated"]["icon"] == "stats"
    # The already-seen entries from the first connection must not reappear.
    dumped = json.dumps(resumed)
    assert "First reply" not in dumped
    assert "First title" not in dumped

    await _cleanup_turn_state(conversation_id)
    await _cleanup_user_events(_USER_ID)


@pytest.mark.asyncio
async def test_sse_404_for_nonexistent_conversation(sse_client: AsyncClient) -> None:
    response = await sse_client.get(
        f"/conversations/{uuid4()}/events",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Conversation not found"


@pytest.mark.asyncio
async def test_sse_404_for_another_users_conversation(sse_client: AsyncClient) -> None:
    conversation = await _create_conversation(_OTHER_USER_ID, "Not yours")

    response = await sse_client.get(
        f"/conversations/{conversation.id}/events",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Conversation not found"
