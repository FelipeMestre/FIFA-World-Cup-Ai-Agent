"""Integration tests for `GET /api/v1/conversations/{id}/watch`. Uses real
Postgres and Redis (no mocking, per AGENTS.md's testing anti-pattern table)
and `app.dependency_overrides` for auth, mirroring
`test_conversation_endpoints.py`'s conventions. Seeds the Redis stream with
real `serialize_chat_turn_event` output (the same function the job itself
uses) rather than hand-crafted JSON, so these tests fail if the job's wire
format and the watch endpoint's parsing of it ever drift apart.
"""

import json
from collections.abc import AsyncGenerator
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from src.api.v1.auth.services.dependencies import parse_jwt_data
from src.domain.chat.services.chat_service import ContentDeltaEvent, MessageDoneEvent
from src.infra.postgres.config import SessionFactory
from src.infra.postgres.repositories.conversation_repository import (
    _SqlAlchemyConversationRepository,
)
from src.infra.redis.config import redis_client
from src.infra.task_queue.chat_tasks import (
    serialize_chat_turn_event,
    turn_in_progress_key,
    turn_stream_key,
)
from src.main import app

_USER_ID = 990901
_OTHER_USER_ID = 990902


def _parse_sse(body: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    event_type: str | None = None
    for line in body.splitlines():
        if line.startswith("event:"):
            event_type = line.removeprefix("event:").strip()
        elif line.startswith("data:"):
            assert event_type is not None
            events.append((event_type, json.loads(line.removeprefix("data:").strip())))
            event_type = None
    return events


@pytest.fixture(autouse=True)
async def _seed_users_and_cleanup() -> AsyncGenerator[None]:
    async with SessionFactory() as session:
        for user_id in (_USER_ID, _OTHER_USER_ID):
            await session.execute(
                text(
                    'INSERT INTO "user" (id, email, password_hash, is_admin, created_at) '
                    "VALUES (:id, :email, 'hash', false, now())"
                ),
                {"id": user_id, "email": f"watch-turn-test-{user_id}@example.test"},
            )
        await session.commit()
    yield
    async with SessionFactory() as cleanup_session:
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


async def _create_conversation(user_id: int = _USER_ID) -> str:
    async with SessionFactory() as session:
        repo = _SqlAlchemyConversationRepository(session)
        conversation = await repo.get_or_create(uuid4(), user_id, "Watch test conversation")
        await session.commit()
        return str(conversation.id)


@pytest.mark.asyncio
async def test_watch_returns_204_when_no_turn_in_progress(client: AsyncClient) -> None:
    conversation_id = await _create_conversation()

    response = await client.get(
        f"/api/v1/conversations/{conversation_id}/watch",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 204
    assert response.text == ""


@pytest.mark.asyncio
async def test_watch_404_for_another_users_conversation(client: AsyncClient) -> None:
    conversation_id = await _create_conversation(user_id=_OTHER_USER_ID)

    response = await client.get(
        f"/api/v1/conversations/{conversation_id}/watch",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_watch_404_for_nonexistent_conversation(client: AsyncClient) -> None:
    response = await client.get(
        f"/api/v1/conversations/{uuid4()}/watch",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_watch_streams_backlog_and_stops_at_the_terminal_event(client: AsyncClient) -> None:
    conversation_id = await _create_conversation()
    stream_key = turn_stream_key(conversation_id)
    progress_key = turn_in_progress_key(conversation_id)

    # Seed the stream exactly as the real job would, using its own
    # serializer -- then clear the in-progress flag the way the job's
    # `finally` does, simulating "already finished by the time we connect".
    await redis_client.xadd(
        stream_key, serialize_chat_turn_event(ContentDeltaEvent(content="Here's "))
    )
    await redis_client.xadd(
        stream_key, serialize_chat_turn_event(ContentDeltaEvent(content="the answer."))
    )
    await redis_client.xadd(
        stream_key,
        serialize_chat_turn_event(
            MessageDoneEvent(
                conversation_id=conversation_id,
                content="Here's the answer.",
                model="anthropic/claude-sonnet-4.5",
                content_segments=["Here's the answer."],
            )
        ),
    )
    # Flag still set, as it would be right up until the job's own `finally`
    # clears it -- the endpoint's initial check just needs it present to
    # start streaming; the terminal entry already in the backlog is what
    # actually ends the stream, not the flag's state at that point.
    await redis_client.set(progress_key, "1", ex=60)

    response = await client.get(
        f"/api/v1/conversations/{conversation_id}/watch",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(response.text)

    assert [event_type for event_type, _data in events] == [
        "content_delta",
        "content_delta",
        "message_done",
    ]
    assert events[0][1] == {"content": "Here's "}
    assert events[1][1] == {"content": "the answer."}
    done_type, done_data = events[-1]
    assert done_data["conversation_id"] == conversation_id
    assert done_data["parts"] == [{"type": "text", "content": "Here's the answer."}]

    await redis_client.delete(stream_key, progress_key)
