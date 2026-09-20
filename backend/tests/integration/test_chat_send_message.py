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

import pytest
from httpx import AsyncClient

from src.api.v1.auth.services.dependencies import parse_jwt_data
from src.domain.chat.model.message import Message
from src.infra.openrouter.client import get_openrouter_client
from src.infra.openrouter.schemas import ChatCompletionChunk, ToolCall
from src.infra.redis.repositories.conversation_cache_repository import (
    get_conversation_cache_repository,
)
from src.main import app

_REPLY_CONTENT = "The 2026 World Cup group stage runs from June to July."
_TIME_REPLY_CONTENT = "It is currently the time returned by the tool."


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
def _override_chat_dependencies(
    fake_conversation_cache: _FakeConversationCacheRepository,
) -> AsyncGenerator[None]:
    def fake_jwt_data() -> dict[str, Any]:
        return {"sub": "1", "is_admin": False}

    app.dependency_overrides[parse_jwt_data] = fake_jwt_data
    app.dependency_overrides[get_openrouter_client] = lambda: _FakeOpenRouterClient()
    app.dependency_overrides[get_conversation_cache_repository] = lambda: fake_conversation_cache
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_plain_message_streams_content_delta_then_message_done(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/chat/messages",
        json={"message": "When does the 2026 World Cup group stage run?"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(response.text)

    assert [event_type for event_type, _ in events] == ["content_delta", "message_done"]
    content_event_type, content_data = events[0]
    assert content_data == {"content": _REPLY_CONTENT}

    done_event_type, done_data = events[1]
    assert done_data["conversation_id"]
    assert done_data["parts"] == [{"type": "text", "content": _REPLY_CONTENT}]
    assert done_data["model"] == "anthropic/claude-sonnet-4.5"


@pytest.mark.asyncio
async def test_tool_triggering_message_streams_tool_call_then_message_done(
    client: AsyncClient,
) -> None:
    app.dependency_overrides[get_openrouter_client] = lambda: _ToolTriggeringOpenRouterClient()

    response = await client.post(
        "/api/v1/chat/messages",
        json={"message": "What time is it right now?"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    events = _parse_sse(response.text)

    event_types = [event_type for event_type, _ in events]
    assert event_types == ["tool_call", "content_delta", "message_done"]
    assert events[0][1] == {"name": "get_current_utc_time"}
    assert events[-1][1]["parts"] == [{"type": "text", "content": _TIME_REPLY_CONTENT}]


@pytest.mark.asyncio
async def test_malformed_tool_arguments_do_not_crash_the_stream(client: AsyncClient) -> None:
    app.dependency_overrides[get_openrouter_client] = lambda: _MalformedToolArgsOpenRouterClient()

    response = await client.post(
        "/api/v1/chat/messages",
        json={"message": "What time is it right now?"},
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
        json={"message": "Keep looping forever"},
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
    response = await client.post(
        "/api/v1/chat/messages",
        json={"message": "When does the 2026 World Cup group stage run?"},
        headers={"Authorization": "Bearer test-token"},
    )

    events = _parse_sse(response.text)
    conversation_id = events[-1][1]["conversation_id"]

    persisted = fake_conversation_cache.store[conversation_id]
    assert [m.role for m in persisted] == ["user", "assistant"]
    assert persisted[-1].content == _REPLY_CONTENT
