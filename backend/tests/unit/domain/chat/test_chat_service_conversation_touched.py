"""`ChatService` must touch the conversation and announce the real DB
`updated_at` on the per-user stream: when the user's message is persisted
and again when the assistant turn is persisted. Publishing is fail-soft.
Fakes are real in-memory implementations (no Mock/patch of the DB); module
collaborators (`redis_client`, `SessionFactory`, repo factories) are swapped
with `monkeypatch.setattr`.
"""

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from src.domain.chat.services import chat_service as chat_service_module
from src.domain.chat.services.chat_service import ChatService
from src.domain.chat.services.chat_turn_events import MessageDoneEvent, PersistenceFailedEvent
from src.infra.openrouter.schemas import ChatCompletionChunk
from src.infra.task_queue import chat_streams
from src.infra.task_queue.chat_streams import user_events_key

_USER_ID = 7
_TOUCHED_AT = datetime(2026, 7, 1, 12, 30, tzinfo=UTC)


class _Session:
    def __init__(self, log: list[str]) -> None:
        self._log = log

    async def commit(self) -> None:
        self._log.append("commit")

    async def __aenter__(self) -> "_Session":
        return self

    async def __aexit__(self, *_exc) -> None:
        return None


class _ConversationRepo:
    def __init__(self, log: list[str]) -> None:
        self._log = log

    async def touch(self, conversation_id: UUID) -> datetime:
        self._log.append("touch")
        return _TOUCHED_AT


class _MessageRepo:
    def __init__(self, log: list[str]) -> None:
        self._log = log

    async def append_message(self, conversation_id, role, content, widgets=None, metadata=None):
        self._log.append(f"append:{role}")
        return object()

    async def list_prompt_turns(self, conversation_id):
        return []


class _Redis:
    """In-memory stand-in for `xadd`; `fail` simulates a Redis outage."""

    def __init__(self, log: list[str], fail: bool = False) -> None:
        self._log = log
        self._fail = fail
        self.entries: list[tuple[str, dict]] = []

    async def xadd(self, key: str, fields: dict, maxlen: int | None = None) -> str:
        if self._fail:
            raise ConnectionError("redis down")
        self._log.append("xadd")
        self.entries.append((key, fields))
        return "1-0"


class _Cache:
    async def get_history(self, conversation_id: str):
        return []

    async def save_history(self, conversation_id: str, messages, ttl_seconds: int) -> None:
        return None


class _Llm:
    async def create_chat_completion(self, messages, tools=None) -> AsyncIterator:
        yield ChatCompletionChunk(delta_content="answer", finish_reason="stop", model="m")


def _build(monkeypatch, redis: _Redis, log: list[str]) -> ChatService:
    monkeypatch.setattr(chat_streams, "redis_client", redis)
    monkeypatch.setattr(chat_service_module, "SessionFactory", lambda: _Session(log))
    monkeypatch.setattr(
        chat_service_module, "get_chat_message_repository", lambda _s: _MessageRepo(log)
    )
    monkeypatch.setattr(
        chat_service_module, "get_conversation_repository", lambda _s: _ConversationRepo(log)
    )
    return ChatService(
        conversation_cache=_Cache(),
        openrouter_client=_Llm(),
        tool_registry={},
        conversation_repo=_ConversationRepo(log),
        chat_message_repo=_MessageRepo(log),
        match_repo=None,
        national_team_repo=None,
        session=_Session(log),
    )


def _assert_touched_entry(redis: _Redis, conversation_id: UUID) -> None:
    assert len(redis.entries) == 1
    key, fields = redis.entries[0]
    assert key == user_events_key(_USER_ID)
    assert fields["event_type"] == "ConversationTouchedEvent"
    assert json.loads(fields["payload"]) == {
        "conversation_id": str(conversation_id),
        "updated_at": _TOUCHED_AT.isoformat(),
    }


@pytest.mark.asyncio
async def test_persist_user_message_touches_in_same_transaction_and_publishes_after_commit(
    monkeypatch,
) -> None:
    log: list[str] = []
    redis = _Redis(log)
    service = _build(monkeypatch, redis, log)
    conversation_id = uuid4()

    await service.persist_user_message(conversation_id, _USER_ID, "hi")

    assert log == ["append:user", "touch", "commit", "xadd"]
    _assert_touched_entry(redis, conversation_id)


@pytest.mark.asyncio
async def test_persist_user_message_survives_publish_failure(monkeypatch) -> None:
    log: list[str] = []
    service = _build(monkeypatch, _Redis(log, fail=True), log)

    await service.persist_user_message(uuid4(), _USER_ID, "hi")

    assert log == ["append:user", "touch", "commit"]


@pytest.mark.asyncio
async def test_end_of_turn_publishes_touched_after_commit(monkeypatch) -> None:
    log: list[str] = []
    redis = _Redis(log)
    service = _build(monkeypatch, redis, log)
    conversation_id = uuid4()

    events = [e async for e in service.send_message(conversation_id, _USER_ID, "hi")]

    assert log == ["append:assistant", "touch", "commit", "xadd"]
    _assert_touched_entry(redis, conversation_id)
    assert isinstance(events[-1], MessageDoneEvent)


@pytest.mark.asyncio
async def test_end_of_turn_publish_failure_does_not_fail_or_flag_persistence(monkeypatch) -> None:
    log: list[str] = []
    service = _build(monkeypatch, _Redis(log, fail=True), log)

    events = [e async for e in service.send_message(uuid4(), _USER_ID, "hi")]

    assert isinstance(events[-1], MessageDoneEvent)
    assert not any(isinstance(e, PersistenceFailedEvent) for e in events)
