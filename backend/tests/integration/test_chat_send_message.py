"""Integration test for `POST /api/v1/chat/messages`.

Per AGENTS.md's testing guidance, this overrides `OpenRouterClientInterface`
and `ConversationCacheRepositoryInterface` (via `app.dependency_overrides`)
with real fake implementations instead of mocking internals -- proving a
plain, non-tool-triggering message still round-trips end to end now that the
client is an async generator of `ChatCompletionChunk`s that `ChatService`
aggregates itself.
"""

from collections.abc import AsyncGenerator, AsyncIterator
from typing import Any

import pytest
from httpx import AsyncClient

from src.api.v1.auth.services.dependencies import parse_jwt_data
from src.domain.chat.model.message import Message
from src.infra.openrouter.client import get_openrouter_client
from src.infra.openrouter.schemas import ChatCompletionChunk
from src.infra.redis.repositories.conversation_cache_repository import (
    get_conversation_cache_repository,
)
from src.main import app

_REPLY_CONTENT = "The 2026 World Cup group stage runs from June to July."


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
