"""Integration test for `POST /api/v1/chat/messages`.

Per AGENTS.md's testing guidance, this overrides `OpenRouterClientInterface`
and `ConversationCacheRepositoryInterface` (via `app.dependency_overrides`)
with real fake implementations instead of mocking internals -- proving the
endpoint's Server-Sent Events contract end to end: a plain message, a
tool-triggering message, malformed tool-call arguments, and an
iteration-cap trip all stream the expected `event:`/`data:` frame sequence.
"""

import json
from collections.abc import AsyncGenerator, AsyncIterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from src.api.v1.auth.services.dependencies import parse_jwt_data
from src.domain.chat.model.message import Message
from src.infra.openrouter.client import get_openrouter_client
from src.infra.openrouter.schemas import ChatCompletionChunk, ToolCall
from src.infra.postgres.config import SessionFactory
from src.infra.postgres.repositories.chat_message_repository import (
    _SqlAlchemyChatMessageRepository,
)
from src.infra.redis.repositories.conversation_cache_repository import (
    get_conversation_cache_repository,
)
from src.main import app

_REPLY_CONTENT = "The 2026 World Cup group stage runs from June to July."
_TIME_REPLY_CONTENT = "It is currently the time returned by the tool."
_TEAM_REPLY_CONTENT = "Here's how they did."
_SEEDED_TEAM_ID = 990501
_SEEDED_TEAM_NAME = "Test Widget Team"
_SEEDED_TEAM_CODE = "TWT"
_USER_ID = 990601
_OTHER_USER_ID = 990602


def _parse_sse(body: str) -> list[tuple[str, dict]]:
    """Parse a full SSE response body into `(event_type, data)` pairs."""
    events: list[tuple[str, dict]] = []
    for block in body.strip("\n").split("\n\n"):
        if not block.strip():
            continue
        event_type = None
        data_line = None
        for line in block.splitlines():
            if line.startswith("event:"):
                event_type = line.removeprefix("event:").strip()
            elif line.startswith("data:"):
                data_line = line.removeprefix("data:").strip()
        assert event_type is not None
        assert data_line is not None
        events.append((event_type, json.loads(data_line)))
    return events


class _FakeOpenRouterClient:
    async def create_chat_completion(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> AsyncIterator[ChatCompletionChunk]:
        yield ChatCompletionChunk(delta_content=_REPLY_CONTENT)
        yield ChatCompletionChunk(
            finish_reason="stop",
            model="anthropic/claude-sonnet-4.5",
            tool_calls=[],
        )


class _ToolTriggeringOpenRouterClient:
    """First call requests `get_current_utc_time`; second call (after the
    tool result is appended) returns a final answer.
    """

    def __init__(self) -> None:
        self._call_count = 0

    async def create_chat_completion(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> AsyncIterator[ChatCompletionChunk]:
        self._call_count += 1
        if self._call_count == 1:
            yield ChatCompletionChunk(
                finish_reason="tool_calls",
                model="anthropic/claude-sonnet-4.5",
                tool_calls=[ToolCall(id="call-1", name="get_current_utc_time", arguments="{}")],
            )
            return
        yield ChatCompletionChunk(delta_content=_TIME_REPLY_CONTENT)
        yield ChatCompletionChunk(
            finish_reason="stop", model="anthropic/claude-sonnet-4.5", tool_calls=[]
        )


class _TeamAnalysisTriggeringOpenRouterClient:
    """First call requests `get_team_analysis`; second call (after the real
    repository's result is appended) returns a final answer -- proves the
    widget wiring end to end, through the real DB-backed tool.
    """

    def __init__(self, team_name: str) -> None:
        self._team_name = team_name
        self._call_count = 0

    async def create_chat_completion(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> AsyncIterator[ChatCompletionChunk]:
        self._call_count += 1
        if self._call_count == 1:
            yield ChatCompletionChunk(
                finish_reason="tool_calls",
                model="anthropic/claude-sonnet-4.5",
                tool_calls=[
                    ToolCall(
                        id="call-1",
                        name="get_team_analysis",
                        arguments=json.dumps({"team_name": self._team_name}),
                    )
                ],
            )
            return
        yield ChatCompletionChunk(delta_content=_TEAM_REPLY_CONTENT)
        yield ChatCompletionChunk(
            finish_reason="stop", model="anthropic/claude-sonnet-4.5", tool_calls=[]
        )


class _MalformedToolArgsOpenRouterClient:
    """First call sends invalid arguments for the dummy tool; second call
    (after the executor's rejection message is appended) returns a final
    answer -- proves the loop never crashes on malformed arguments.
    """

    def __init__(self) -> None:
        self._call_count = 0

    async def create_chat_completion(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> AsyncIterator[ChatCompletionChunk]:
        self._call_count += 1
        if self._call_count == 1:
            yield ChatCompletionChunk(
                finish_reason="tool_calls",
                model="anthropic/claude-sonnet-4.5",
                tool_calls=[
                    ToolCall(
                        id="call-1",
                        name="get_current_utc_time",
                        arguments='{"unexpected": "value"}',
                    )
                ],
            )
            return
        yield ChatCompletionChunk(delta_content="Apologies, I couldn't use that tool.")
        yield ChatCompletionChunk(
            finish_reason="stop", model="anthropic/claude-sonnet-4.5", tool_calls=[]
        )


class _AlwaysToolCallingOpenRouterClient:
    """Always requests the tool, never returns `finish_reason: stop` --
    proves the 5-iteration cap trips through the full router path.
    """

    def __init__(self) -> None:
        self._call_count = 0

    async def create_chat_completion(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> AsyncIterator[ChatCompletionChunk]:
        self._call_count += 1
        yield ChatCompletionChunk(delta_content=f"Attempt {self._call_count}. ")
        yield ChatCompletionChunk(
            finish_reason="tool_calls",
            model="anthropic/claude-sonnet-4.5",
            tool_calls=[
                ToolCall(id=f"call-{self._call_count}", name="get_current_utc_time", arguments="{}")
            ],
        )


class _FakeConversationCacheRepository:
    def __init__(self) -> None:
        self._store: dict[str, list[Message]] = {}

    async def get_history(self, conversation_id: str) -> list[Message]:
        return list(self._store.get(conversation_id, []))

    async def save_history(
        self, conversation_id: str, messages: list[Message], ttl_seconds: int
    ) -> None:
        self._store[conversation_id] = list(messages)

    @property
    def store(self) -> dict[str, list[Message]]:
        return self._store


@pytest.fixture
def fake_conversation_cache() -> _FakeConversationCacheRepository:
    return _FakeConversationCacheRepository()


@pytest.fixture(autouse=True)
async def _seed_chat_users() -> AsyncGenerator[None]:
    """`conversation.user_id` is a real FK to `user.id` -- T4 makes
    `POST /chat/messages` write a `conversation` row, so a fake JWT `sub`
    with no backing `user` row now fails the FK constraint. Seeds real
    `user` rows for the fake JWT `sub`s used below and cleans up everything
    a test run creates under them (widgets -> messages -> conversations ->
    users, respecting FK order), mirroring
    `test_chat_message_repository.py`'s `db_session` fixture.
    """
    async with SessionFactory() as session:
        for user_id in (_USER_ID, _OTHER_USER_ID):
            await session.execute(
                text(
                    'INSERT INTO "user" (id, email, password_hash, is_admin, created_at) '
                    "VALUES (:id, :email, 'hash', false, now())"
                ),
                {"id": user_id, "email": f"chat-send-message-test-{user_id}@example.test"},
            )
        await session.commit()
    yield
    async with SessionFactory() as cleanup_session:
        await cleanup_session.execute(
            text(
                "DELETE FROM chat_message_widget WHERE message_id IN "
                "(SELECT id FROM chat_message WHERE conversation_id IN "
                "(SELECT id FROM conversation WHERE user_id IN (:a, :b)))"
            ),
            {"a": _USER_ID, "b": _OTHER_USER_ID},
        )
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
def _override_chat_dependencies(
    fake_conversation_cache: _FakeConversationCacheRepository,
) -> AsyncGenerator[None]:
    def fake_jwt_data() -> dict[str, Any]:
        return {"sub": str(_USER_ID), "is_admin": False}

    app.dependency_overrides[parse_jwt_data] = fake_jwt_data
    app.dependency_overrides[get_openrouter_client] = lambda: _FakeOpenRouterClient()
    app.dependency_overrides[get_conversation_cache_repository] = lambda: fake_conversation_cache
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_plain_message_streams_content_delta_then_message_done(
    client: AsyncClient,
) -> None:
    conversation_id = str(uuid4())
    response = await client.post(
        "/api/v1/chat/messages",
        json={
            "conversation_id": conversation_id,
            "message": "When does the 2026 World Cup group stage run?",
        },
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(response.text)

    assert [event_type for event_type, _ in events] == ["content_delta", "message_done"]
    content_event_type, content_data = events[0]
    assert content_data == {"content": _REPLY_CONTENT}

    done_event_type, done_data = events[1]
    assert done_data["conversation_id"] == conversation_id
    assert done_data["parts"] == [{"type": "text", "content": _REPLY_CONTENT}]
    assert done_data["model"] == "anthropic/claude-sonnet-4.5"


@pytest.mark.asyncio
async def test_tool_triggering_message_streams_tool_call_then_message_done(
    client: AsyncClient,
) -> None:
    app.dependency_overrides[get_openrouter_client] = lambda: _ToolTriggeringOpenRouterClient()

    response = await client.post(
        "/api/v1/chat/messages",
        json={"conversation_id": str(uuid4()), "message": "What time is it right now?"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    events = _parse_sse(response.text)

    event_types = [event_type for event_type, _ in events]
    assert event_types == ["tool_call", "content_delta", "message_done"]
    assert events[0][1] == {"name": "get_current_utc_time"}
    assert events[-1][1]["parts"] == [{"type": "text", "content": _TIME_REPLY_CONTENT}]


@pytest.fixture
async def seeded_team() -> AsyncGenerator[None]:
    async with SessionFactory() as session:
        await session.execute(
            text(
                "INSERT INTO national_team (team_id, team_name, fifa_code, confederation) "
                "VALUES (:id, :name, :code, 'UEFA')"
            ),
            {"id": _SEEDED_TEAM_ID, "name": _SEEDED_TEAM_NAME, "code": _SEEDED_TEAM_CODE},
        )
        await session.commit()
    yield
    async with SessionFactory() as session:
        await session.execute(
            text("DELETE FROM national_team WHERE team_id = :id"), {"id": _SEEDED_TEAM_ID}
        )
        await session.commit()


@pytest.mark.asyncio
async def test_team_analysis_tool_streams_widget_ready_then_message_done(
    client: AsyncClient, seeded_team: None
) -> None:
    app.dependency_overrides[get_openrouter_client] = lambda: (
        _TeamAnalysisTriggeringOpenRouterClient(_SEEDED_TEAM_NAME)
    )

    response = await client.post(
        "/api/v1/chat/messages",
        json={"conversation_id": str(uuid4()), "message": f"How is {_SEEDED_TEAM_NAME} doing?"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    events = _parse_sse(response.text)

    event_types = [event_type for event_type, _ in events]
    # The widget arrives before the final text -- the tool resolves in the
    # first iteration, well before the model's answer streams in the second.
    assert event_types == ["tool_call", "widget_ready", "content_delta", "message_done"]

    widget_event_type, widget_data = events[1]
    assert widget_event_type == "widget_ready"
    assert widget_data["part"]["type"] == "team_widget"
    assert widget_data["part"]["data"]["id"] == str(_SEEDED_TEAM_ID)
    assert widget_data["part"]["data"]["code"] == _SEEDED_TEAM_CODE
    assert widget_data["part"]["data"]["name"] == _SEEDED_TEAM_NAME

    done_event_type, done_data = events[-1]
    assert done_event_type == "message_done"
    assert done_data["parts"] == [
        {"type": "text", "content": _TEAM_REPLY_CONTENT},
        widget_data["part"],
    ]


@pytest.mark.asyncio
async def test_malformed_tool_arguments_do_not_crash_the_stream(client: AsyncClient) -> None:
    app.dependency_overrides[get_openrouter_client] = lambda: _MalformedToolArgsOpenRouterClient()

    response = await client.post(
        "/api/v1/chat/messages",
        json={"conversation_id": str(uuid4()), "message": "What time is it right now?"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    events = _parse_sse(response.text)

    assert events[-1][0] == "message_done"
    assert events[-1][1]["parts"] == [
        {"type": "text", "content": "Apologies, I couldn't use that tool."}
    ]


@pytest.mark.asyncio
async def test_iteration_cap_emits_cap_reached_then_message_done(
    client: AsyncClient,
) -> None:
    app.dependency_overrides[get_openrouter_client] = lambda: _AlwaysToolCallingOpenRouterClient()

    response = await client.post(
        "/api/v1/chat/messages",
        json={"conversation_id": str(uuid4()), "message": "Keep looping forever"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    events = _parse_sse(response.text)

    event_types = [event_type for event_type, _ in events]
    # A dedicated cap_reached event precedes message_done, per the locked
    # spec behavior -- never silence, never a raw error.
    assert event_types[-2:] == ["cap_reached", "message_done"]

    cap_reached_data = events[-2][1]
    assert "Attempt 1." in cap_reached_data["content"]
    assert "Attempt 5." in cap_reached_data["content"]
    assert "clarify" in cap_reached_data["clarification"].lower()

    final_text = events[-1][1]["parts"][0]["content"]
    assert "Attempt 1." in final_text
    assert "Attempt 5." in final_text
    assert "clarify" in final_text.lower()


@pytest.mark.asyncio
async def test_conversation_history_persisted_to_cache_after_stream_completes(
    client: AsyncClient, fake_conversation_cache: _FakeConversationCacheRepository
) -> None:
    conversation_id = str(uuid4())
    response = await client.post(
        "/api/v1/chat/messages",
        json={
            "conversation_id": conversation_id,
            "message": "When does the 2026 World Cup group stage run?",
        },
        headers={"Authorization": "Bearer test-token"},
    )

    events = _parse_sse(response.text)
    assert events[-1][1]["conversation_id"] == conversation_id

    persisted = fake_conversation_cache.store[conversation_id]
    assert [m.role for m in persisted] == ["user", "assistant"]
    assert persisted[-1].content == _REPLY_CONTENT


@pytest.mark.asyncio
async def test_conversation_history_persisted_to_postgres_after_stream_completes(
    client: AsyncClient,
) -> None:
    """(c) -- the Postgres write happens after a successful `send_message`
    call: assert rows exist via the T3 repository rather than mocking
    anything, per AGENTS.md's testing anti-pattern table."""
    conversation_id = str(uuid4())
    response = await client.post(
        "/api/v1/chat/messages",
        json={
            "conversation_id": conversation_id,
            "message": "When does the 2026 World Cup group stage run?",
        },
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200

    async with SessionFactory() as session:
        chat_message_repository = _SqlAlchemyChatMessageRepository(session)
        messages = await chat_message_repository.list_for_conversation(
            UUID(conversation_id), _USER_ID
        )

    assert [(m.sequence, m.role, m.content) for m in messages] == [
        (1, "user", "When does the 2026 World Cup group stage run?"),
        (2, "assistant", _REPLY_CONTENT),
    ]


@pytest.mark.asyncio
async def test_two_messages_in_same_conversation_persist_both_turns_in_sequence(
    client: AsyncClient,
) -> None:
    """(a) -- sending two messages in the same conversation persists both
    turns with correct `sequence`."""
    conversation_id = str(uuid4())

    first_response = await client.post(
        "/api/v1/chat/messages",
        json={"conversation_id": conversation_id, "message": "First message"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert first_response.status_code == 200

    second_response = await client.post(
        "/api/v1/chat/messages",
        json={"conversation_id": conversation_id, "message": "Second message"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert second_response.status_code == 200

    async with SessionFactory() as session:
        chat_message_repository = _SqlAlchemyChatMessageRepository(session)
        messages = await chat_message_repository.list_for_conversation(
            UUID(conversation_id), _USER_ID
        )

    assert [(m.sequence, m.role, m.content) for m in messages] == [
        (1, "user", "First message"),
        (2, "assistant", _REPLY_CONTENT),
        (3, "user", "Second message"),
        (4, "assistant", _REPLY_CONTENT),
    ]


@pytest.mark.asyncio
async def test_posting_to_another_users_conversation_id_is_forbidden(
    client: AsyncClient,
) -> None:
    """(b) -- a second user attempting to post to another user's
    `conversation_id` gets a 403."""
    conversation_id = str(uuid4())

    owner_response = await client.post(
        "/api/v1/chat/messages",
        json={"conversation_id": conversation_id, "message": "First message"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert owner_response.status_code == 200

    app.dependency_overrides[parse_jwt_data] = lambda: {
        "sub": str(_OTHER_USER_ID),
        "is_admin": False,
    }

    intruder_response = await client.post(
        "/api/v1/chat/messages",
        json={"conversation_id": conversation_id, "message": "Trying to hijack this thread"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert intruder_response.status_code == 403
