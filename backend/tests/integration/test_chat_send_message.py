"""Integration test for `POST /api/v1/chat/messages`.

Per AGENTS.md's testing guidance, this overrides `OpenRouterClientInterface`
and `ConversationCacheRepositoryInterface` (via `app.dependency_overrides`)
with real fake implementations instead of mocking internals -- proving a
plain, non-tool-triggering message still round-trips end to end now that the
client is an async generator of `ChatCompletionChunk`s that `ChatService`
delegates to `ToolCallExecutor` to aggregate, and that the bounded
tool-execution loop (tool trigger/resolve, malformed-args rejection,
iteration-cap trip) works through the full router path.
"""

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


@pytest.fixture(autouse=True)
def _override_chat_dependencies() -> AsyncGenerator[None]:
    def fake_jwt_data() -> dict[str, Any]:
        return {"sub": "1", "is_admin": False}

    app.dependency_overrides[parse_jwt_data] = fake_jwt_data
    app.dependency_overrides[get_openrouter_client] = lambda: _FakeOpenRouterClient()
    app.dependency_overrides[get_conversation_cache_repository] = lambda: (
        _FakeConversationCacheRepository()
    )
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_plain_message_round_trips_via_chat_completion_result(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/chat/messages",
        json={"message": "When does the 2026 World Cup group stage run?"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["conversation_id"]
    assert body["reply"]["parts"] == [{"type": "text", "content": _REPLY_CONTENT}]


@pytest.mark.asyncio
async def test_tool_triggering_message_resolves_to_final_answer(client: AsyncClient) -> None:
    app.dependency_overrides[get_openrouter_client] = lambda: _ToolTriggeringOpenRouterClient()

    response = await client.post(
        "/api/v1/chat/messages",
        json={"message": "What time is it right now?"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["reply"]["parts"] == [{"type": "text", "content": _TIME_REPLY_CONTENT}]


@pytest.mark.asyncio
async def test_malformed_tool_arguments_do_not_crash_the_loop(client: AsyncClient) -> None:
    app.dependency_overrides[get_openrouter_client] = lambda: _MalformedToolArgsOpenRouterClient()

    response = await client.post(
        "/api/v1/chat/messages",
        json={"message": "What time is it right now?"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["reply"]["parts"] == [
        {"type": "text", "content": "Apologies, I couldn't use that tool."}
    ]


@pytest.mark.asyncio
async def test_iteration_cap_returns_partial_content_and_clarification(
    client: AsyncClient,
) -> None:
    app.dependency_overrides[get_openrouter_client] = lambda: _AlwaysToolCallingOpenRouterClient()

    response = await client.post(
        "/api/v1/chat/messages",
        json={"message": "Keep looping forever"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    body = response.json()
    reply_text = body["reply"]["parts"][0]["content"]
    # Best-effort partial content is present (never silently discarded)...
    assert "Attempt 1." in reply_text
    assert "Attempt 5." in reply_text
    # ...followed by a clarification ask, not a raw error.
    assert "clarify" in reply_text.lower()
