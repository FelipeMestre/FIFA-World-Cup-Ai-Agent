"""Integration tests for `GET /users/events`, the dedicated per-user SSE
endpoint added in T6 to fix cross-window sync: a device with no conversation
open (or a different one open) previously had no live connection at all, so
a conversation created in one browser window never appeared in another
window's sidebar.

Same real-`uvicorn.Server`-on-a-free-port pattern `test_conversation_events.py`
uses and documents in its own module docstring -- `httpx.ASGITransport`
fully buffers the response before returning anything, which never happens
against this endpoint's deliberately-infinite generator.
"""

import asyncio
import json
import socket
from collections.abc import AsyncGenerator, AsyncIterator
from typing import Any

import pytest
import uvicorn
from httpx import AsyncClient
from sqlalchemy import text

from src.api.v1.auth.services.dependencies import parse_jwt_data
from src.infra.postgres.config import SessionFactory
from src.infra.redis.config import redis_client
from src.infra.task_queue.chat_streams import (
    STREAM_CURSOR_ORIGIN,
    ConversationCategorizedEvent,
    ConversationCreatedEvent,
    serialize_conversation_categorized_event,
    serialize_conversation_created_event,
    user_events_key,
)
from src.main import app

_USER_ID = 990911


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
async def _seed_user() -> AsyncGenerator[None]:
    async with SessionFactory() as session:
        # `name` is passed as its own bound parameter rather than derived in
        # SQL from a reused `:email` -- see the identical note in
        # `test_conversation_events.py` for why (pre-existing asyncpg
        # `AmbiguousParameterError`, unrelated to this task).
        await session.execute(
            text(
                'INSERT INTO "user" (id, email, name, password_hash, is_admin, created_at) '
                "VALUES (:id, :email, :name, 'hash', false, now())"
            ),
            {
                "id": _USER_ID,
                "email": f"user-events-test-{_USER_ID}@example.test",
                "name": f"user-events-test-{_USER_ID}",
            },
        )
        await session.commit()
    yield
    async with SessionFactory() as cleanup_session:
        await cleanup_session.execute(text('DELETE FROM "user" WHERE id = :id'), {"id": _USER_ID})
        await cleanup_session.commit()
    await redis_client.delete(user_events_key(_USER_ID))


@pytest.fixture(autouse=True)
def _override_auth() -> AsyncGenerator[None]:
    def fake_jwt_data() -> dict[str, Any]:
        return {"sub": str(_USER_ID), "is_admin": False}

    app.dependency_overrides[parse_jwt_data] = fake_jwt_data
    yield
    app.dependency_overrides.clear()


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
async def test_user_events_delivers_a_pre_seeded_conversation_created_entry(
    sse_client: AsyncClient,
) -> None:
    await redis_client.xadd(
        user_events_key(_USER_ID),
        serialize_conversation_created_event(
            ConversationCreatedEvent(
                conversation_id="11111111-1111-1111-1111-111111111111",
                title="New conversation",
                created_at="2026-09-24T12:00:00+00:00",
            )
        ),
    )

    async with sse_client.stream(
        "GET",
        "/users/events",
        headers={"Authorization": "Bearer test-token", "Last-Event-ID": STREAM_CURSOR_ORIGIN},
    ) as response:
        assert response.status_code == 200
        lines = response.aiter_lines()
        entry_id, event_name, data = await asyncio.wait_for(_read_frame(lines), timeout=5)

    assert event_name == "conversation_created"
    assert data == {
        "type": "conversation_created",
        "cursor": entry_id,
        "conversation_id": "11111111-1111-1111-1111-111111111111",
        "title": "New conversation",
        "created_at": "2026-09-24T12:00:00+00:00",
    }


@pytest.mark.asyncio
async def test_user_events_delivers_a_pre_seeded_conversation_categorized_entry(
    sse_client: AsyncClient,
) -> None:
    await redis_client.xadd(
        user_events_key(_USER_ID),
        serialize_conversation_categorized_event(
            ConversationCategorizedEvent(
                conversation_id="22222222-2222-2222-2222-222222222222",
                title="Injury update: Player X",
                icon="injury",
            )
        ),
    )

    async with sse_client.stream(
        "GET",
        "/users/events",
        headers={"Authorization": "Bearer test-token", "Last-Event-ID": STREAM_CURSOR_ORIGIN},
    ) as response:
        assert response.status_code == 200
        lines = response.aiter_lines()
        entry_id, event_name, data = await asyncio.wait_for(_read_frame(lines), timeout=5)

    assert event_name == "conversation_updated"
    assert data == {
        "type": "conversation_updated",
        "cursor": entry_id,
        "conversation_id": "22222222-2222-2222-2222-222222222222",
        "title": "Injury update: Player X",
        "icon": "injury",
    }


@pytest.mark.asyncio
async def test_user_events_resume_from_last_event_id_does_not_redeliver_seen_entries(
    sse_client: AsyncClient,
) -> None:
    await redis_client.xadd(
        user_events_key(_USER_ID),
        serialize_conversation_created_event(
            ConversationCreatedEvent(
                conversation_id="33333333-3333-3333-3333-333333333333",
                title="First conversation",
                created_at="2026-09-24T12:00:00+00:00",
            )
        ),
    )

    async with sse_client.stream(
        "GET",
        "/users/events",
        headers={"Authorization": "Bearer test-token", "Last-Event-ID": STREAM_CURSOR_ORIGIN},
    ) as response:
        assert response.status_code == 200
        lines = response.aiter_lines()
        captured_id, first_event, _first_data = await asyncio.wait_for(
            _read_frame(lines), timeout=5
        )

    assert first_event == "conversation_created"

    await redis_client.xadd(
        user_events_key(_USER_ID),
        serialize_conversation_categorized_event(
            ConversationCategorizedEvent(
                conversation_id="33333333-3333-3333-3333-333333333333",
                title="Second title",
                icon="stats",
            )
        ),
    )

    async with sse_client.stream(
        "GET",
        "/users/events",
        headers={"Authorization": "Bearer test-token", "Last-Event-ID": captured_id},
    ) as response:
        assert response.status_code == 200
        lines = response.aiter_lines()
        _resumed_id, resumed_event, resumed_data = await asyncio.wait_for(
            _read_frame(lines), timeout=5
        )

    assert resumed_event == "conversation_updated"
    assert resumed_data["title"] == "Second title"
    # The already-seen entry from the first connection must not reappear.
    assert "First conversation" not in json.dumps(resumed_data)
