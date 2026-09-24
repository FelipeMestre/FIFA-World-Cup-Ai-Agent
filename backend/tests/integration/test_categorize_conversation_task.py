"""Integration tests for `categorize_conversation_task`. Same pattern as
`test_generate_chat_reply_task.py`: runs the task function directly against
real Postgres and Redis, substituting only the OpenRouter client (an
external service) by monkeypatching the task module's import site.
"""

import json
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from src.infra.openrouter.schemas import ChatCompletionChunk
from src.infra.postgres.config import SessionFactory
from src.infra.postgres.repositories.conversation_repository import (
    _SqlAlchemyConversationRepository,
)
from src.infra.redis.config import redis_client
from src.infra.task_queue.chat_streams import user_events_key
from src.infra.task_queue.chat_tasks import categorize_conversation_task

_USER_ID = 990821
_DEFAULT_TITLE = "Task test conversation"


class _FakeCategorizationClient:
    def __init__(self, response_text: str) -> None:
        self._response_text = response_text

    async def create_chat_completion(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> AsyncIterator[ChatCompletionChunk]:
        yield ChatCompletionChunk(delta_content=self._response_text)
        yield ChatCompletionChunk(finish_reason="stop", model="anthropic/claude-sonnet-4.5")


class _RaisingCategorizationClient:
    async def create_chat_completion(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> AsyncIterator[ChatCompletionChunk]:
        raise RuntimeError("simulated OpenRouter failure")
        yield  # pragma: no cover -- makes this an async generator


@pytest.fixture(autouse=True)
async def _seed_user_and_cleanup():
    async with SessionFactory() as session:
        # `name` is passed as its own bound parameter rather than derived
        # in SQL from a reused `:email` (e.g. `split_part(:email, ...)`) --
        # asyncpg's prepared-statement type inference raises
        # `AmbiguousParameterError` when the same parameter is bound in two
        # different type contexts (`character varying` for the column,
        # `text` for the function argument) in one statement.
        await session.execute(
            text(
                'INSERT INTO "user" (id, email, name, password_hash, is_admin, created_at) '
                "VALUES (:id, :email, :name, 'hash', false, now())"
            ),
            {
                "id": _USER_ID,
                "email": f"categorize-task-test-{_USER_ID}@example.test",
                "name": f"categorize-task-test-{_USER_ID}",
            },
        )
        await session.commit()
    yield
    async with SessionFactory() as cleanup_session:
        await cleanup_session.execute(
            text("DELETE FROM conversation WHERE user_id = :uid"), {"uid": _USER_ID}
        )
        await cleanup_session.execute(text('DELETE FROM "user" WHERE id = :uid'), {"uid": _USER_ID})
        await cleanup_session.commit()
    await redis_client.delete(user_events_key(_USER_ID))


async def _create_conversation() -> str:
    async with SessionFactory() as session:
        repo = _SqlAlchemyConversationRepository(session)
        conversation, _created = await repo.get_or_create(uuid4(), _USER_ID, _DEFAULT_TITLE)
        await session.commit()
        return str(conversation.id)


async def _get_conversation(conversation_id: str):
    async with SessionFactory() as session:
        repo = _SqlAlchemyConversationRepository(session)
        return await repo.get_owned(UUID(conversation_id), _USER_ID)


async def _stream_entries() -> list[tuple[str, dict]]:
    raw = await redis_client.xrange(user_events_key(_USER_ID))
    return [(fields["event_type"], json.loads(fields["payload"])) for _entry_id, fields in raw]


@pytest.mark.asyncio
async def test_categorize_conversation_task_persists_title_and_icon_on_success(monkeypatch):
    response_text = json.dumps({"title": "Squad injury update", "icon": "injury"})
    monkeypatch.setattr(
        "src.infra.task_queue.chat_tasks.get_openrouter_client",
        lambda: _FakeCategorizationClient(response_text),
    )
    conversation_id = await _create_conversation()

    await categorize_conversation_task(
        {}, conversation_id, _USER_ID, "Who's injured on the USA squad?"
    )

    conversation = await _get_conversation(conversation_id)
    assert conversation is not None
    assert conversation.title == "Squad injury update"
    assert conversation.icon == "injury"

    entries = await _stream_entries()
    assert len(entries) == 1
    event_type, payload = entries[0]
    assert event_type == "ConversationCategorizedEvent"
    assert payload == {
        "conversation_id": conversation_id,
        "title": "Squad injury update",
        "icon": "injury",
    }


@pytest.mark.asyncio
async def test_categorize_conversation_task_noops_on_malformed_json(monkeypatch):
    monkeypatch.setattr(
        "src.infra.task_queue.chat_tasks.get_openrouter_client",
        lambda: _FakeCategorizationClient("this is not json"),
    )
    conversation_id = await _create_conversation()

    await categorize_conversation_task({}, conversation_id, _USER_ID, "Tell me about the final")

    conversation = await _get_conversation(conversation_id)
    assert conversation is not None
    assert conversation.title == _DEFAULT_TITLE
    assert conversation.icon is None
    assert await _stream_entries() == []


@pytest.mark.asyncio
async def test_categorize_conversation_task_noops_on_icon_outside_enum(monkeypatch):
    response_text = json.dumps({"title": "Some title", "icon": "not_a_real_icon"})
    monkeypatch.setattr(
        "src.infra.task_queue.chat_tasks.get_openrouter_client",
        lambda: _FakeCategorizationClient(response_text),
    )
    conversation_id = await _create_conversation()

    await categorize_conversation_task({}, conversation_id, _USER_ID, "Tell me about the final")

    conversation = await _get_conversation(conversation_id)
    assert conversation is not None
    assert conversation.title == _DEFAULT_TITLE
    assert conversation.icon is None
    assert await _stream_entries() == []


@pytest.mark.asyncio
async def test_categorize_conversation_task_noops_on_empty_title(monkeypatch):
    response_text = json.dumps({"title": "   ", "icon": "player"})
    monkeypatch.setattr(
        "src.infra.task_queue.chat_tasks.get_openrouter_client",
        lambda: _FakeCategorizationClient(response_text),
    )
    conversation_id = await _create_conversation()

    await categorize_conversation_task({}, conversation_id, _USER_ID, "Tell me about the final")

    conversation = await _get_conversation(conversation_id)
    assert conversation is not None
    assert conversation.title == _DEFAULT_TITLE
    assert conversation.icon is None
    assert await _stream_entries() == []


@pytest.mark.asyncio
async def test_categorize_conversation_task_swallows_openrouter_failure(monkeypatch):
    monkeypatch.setattr(
        "src.infra.task_queue.chat_tasks.get_openrouter_client",
        lambda: _RaisingCategorizationClient(),
    )
    conversation_id = await _create_conversation()

    # Must not raise -- this is a fire-and-forget best-effort job.
    await categorize_conversation_task({}, conversation_id, _USER_ID, "Tell me about the final")

    conversation = await _get_conversation(conversation_id)
    assert conversation is not None
    assert conversation.title == _DEFAULT_TITLE
    assert conversation.icon is None
    assert await _stream_entries() == []
