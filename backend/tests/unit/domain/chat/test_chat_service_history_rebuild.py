"""`ChatService.send_message` must rebuild the prompt history from Postgres
rows when the Redis history cache is empty, and write it back to the cache.
Fakes below are real in-memory implementations of the interfaces involved
(no Mock/patch); the assistant-persistence step at the end of `send_message`
opens its own DB session and is expected to fail soft here (non-fatal
`PersistenceFailedEvent`), which these tests do not assert on.
"""

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest

from src.domain.chat.model.message import Message
from src.domain.chat.services.chat_history_rebuild_service import ChatHistoryRebuildService
from src.domain.chat.services.chat_service import (
    CONVERSATION_HISTORY_TTL_SECONDS,
    SYSTEM_PROMPT,
    ChatService,
)
from src.infra.openrouter.schemas import ChatCompletionChunk


class _InMemoryConversationCache:
    def __init__(self, initial: list[Message] | None = None) -> None:
        self.history = initial or []
        self.saved: list[tuple[list[tuple[str, str]], int]] = []

    async def get_history(self, conversation_id: str) -> list[Message]:
        return list(self.history)

    async def save_history(
        self, conversation_id: str, messages: list[Message], ttl_seconds: int
    ) -> None:
        self.saved.append(([(m.role, m.content) for m in messages], ttl_seconds))


class _InMemoryPromptTurnSource:
    def __init__(self, rows: list[Message]) -> None:
        self.rows = rows
        self.calls = 0

    async def list_prompt_turns(self, conversation_id) -> list[Message]:
        self.calls += 1
        return list(self.rows)


class _WordCounter:
    def count_tokens(self, text: str) -> int:
        return len(text.split())


class _RecordingLlm:
    def __init__(self) -> None:
        self.received: list[list[dict]] = []

    async def create_chat_completion(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> AsyncIterator[ChatCompletionChunk]:
        self.received.append(list(messages))
        yield ChatCompletionChunk(
            delta_content="fresh answer", finish_reason="stop", model="test-model"
        )


def _service(
    cache: _InMemoryConversationCache, source: _InMemoryPromptTurnSource, llm: _RecordingLlm
) -> ChatService:
    return ChatService(
        conversation_cache=cache,
        openrouter_client=llm,
        tool_registry={},
        conversation_repo=None,
        chat_message_repo=source,
        match_repo=None,
        national_team_repo=None,
        session=None,
        history_rebuild_service=ChatHistoryRebuildService(
            source, _WordCounter(), token_budget=1_000
        ),
    )


async def _drain(service: ChatService, user_message: str) -> None:
    async for _event in service.send_message(uuid4(), 1, user_message):
        pass


_ROWS = [
    Message(role="user", content="who won in 2022"),
    Message(role="assistant", content="Argentina"),
    Message(role="user", content="current question"),  # persisted before send_message
]


@pytest.mark.asyncio
async def test_empty_cache_rebuilds_prior_context_into_the_prompt_without_duplicating_current() -> (
    None
):
    cache, llm = _InMemoryConversationCache(), _RecordingLlm()
    service = _service(cache, _InMemoryPromptTurnSource(_ROWS), llm)

    await _drain(service, "current question")

    assert llm.received[0] == [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "who won in 2022"},
        {"role": "assistant", "content": "Argentina"},
        {"role": "user", "content": "current question"},
    ]


@pytest.mark.asyncio
async def test_rebuilt_history_is_saved_to_the_cache_with_the_existing_ttl() -> None:
    cache, llm = _InMemoryConversationCache(), _RecordingLlm()
    service = _service(cache, _InMemoryPromptTurnSource(_ROWS), llm)

    await _drain(service, "current question")

    rebuilt_only, ttl = cache.saved[0]
    assert rebuilt_only == [("user", "who won in 2022"), ("assistant", "Argentina")]
    assert ttl == CONVERSATION_HISTORY_TTL_SECONDS


@pytest.mark.asyncio
async def test_warm_cache_is_used_as_is_and_postgres_is_not_read() -> None:
    cached = [
        Message(role="user", content="cached q"),
        Message(role="assistant", content="cached a"),
    ]
    cache, llm = _InMemoryConversationCache(cached), _RecordingLlm()
    source = _InMemoryPromptTurnSource(_ROWS)
    service = _service(cache, source, llm)

    await _drain(service, "current question")

    assert source.calls == 0
    assert [m["content"] for m in llm.received[0][1:]] == [
        "cached q",
        "cached a",
        "current question",
    ]


@pytest.mark.asyncio
async def test_first_message_with_nothing_to_rebuild_sends_only_the_current_message() -> None:
    cache, llm = _InMemoryConversationCache(), _RecordingLlm()
    service = _service(
        cache, _InMemoryPromptTurnSource([Message(role="user", content="hello")]), llm
    )

    await _drain(service, "hello")

    assert llm.received[0][1:] == [{"role": "user", "content": "hello"}]
    # Only the post-turn save (history + new turn) happens; no empty rebuilt save.
    assert [h for h, _ttl in cache.saved] == [[("user", "hello"), ("assistant", "fresh answer")]]


@pytest.mark.asyncio
async def test_rebuild_failure_degrades_to_empty_history_instead_of_failing_the_turn() -> None:
    class _BrokenSource(_InMemoryPromptTurnSource):
        async def list_prompt_turns(self, conversation_id) -> list[Message]:
            raise RuntimeError("postgres down")

    cache, llm = _InMemoryConversationCache(), _RecordingLlm()
    service = _service(cache, _BrokenSource([]), llm)

    await _drain(service, "current question")

    assert llm.received[0][1:] == [{"role": "user", "content": "current question"}]
