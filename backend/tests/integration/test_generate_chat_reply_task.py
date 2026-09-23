"""Integration tests for `generate_chat_reply_task`. Runs the task function
directly (it is just a plain async function -- arq itself needs no test
double), against real Postgres and Redis, per AGENTS.md's testing
convention. The OpenRouter client is the one legitimate substitution (an
external service, not the database), injected by monkeypatching the task
module's import site -- the direct equivalent of
`app.dependency_overrides[get_openrouter_client]` used elsewhere in this
suite, since there is no FastAPI request here to override.
"""

import json
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from src.infra.openrouter.schemas import ChatCompletionChunk
from src.infra.postgres.config import SessionFactory
from src.infra.postgres.repositories.chat_message_repository import (
    _SqlAlchemyChatMessageRepository,
)
from src.infra.postgres.repositories.chat_turn_failure_repository import (
    _SqlAlchemyChatTurnFailureRepository,
)
from src.infra.postgres.repositories.conversation_repository import (
    _SqlAlchemyConversationRepository,
)
from src.infra.redis.config import redis_client
from src.infra.task_queue.chat_tasks import (
    generate_chat_reply_task,
    turn_in_progress_key,
    turn_stream_key,
)

_USER_ID = 990801
_REPLY_CONTENT = "Here's the answer."


class _FakeOpenRouterClient:
    async def create_chat_completion(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> AsyncIterator[ChatCompletionChunk]:
        yield ChatCompletionChunk(delta_content=_REPLY_CONTENT)
        yield ChatCompletionChunk(
            finish_reason="stop", model="anthropic/claude-sonnet-4.5", tool_calls=[]
        )


class _FailingOpenRouterClient:
    async def create_chat_completion(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> AsyncIterator[ChatCompletionChunk]:
        raise RuntimeError("simulated OpenRouter failure")
        yield  # pragma: no cover -- makes this an async generator


@pytest.fixture(autouse=True)
async def _seed_user_and_cleanup():
    async with SessionFactory() as session:
        await session.execute(
            text(
                'INSERT INTO "user" (id, email, password_hash, is_admin, created_at) '
                "VALUES (:id, :email, 'hash', false, now())"
            ),
            {"id": _USER_ID, "email": f"chat-reply-task-test-{_USER_ID}@example.test"},
        )
        await session.commit()
    yield
    async with SessionFactory() as cleanup_session:
        await cleanup_session.execute(
            text(
                "DELETE FROM chat_message_widget WHERE message_id IN "
                "(SELECT id FROM chat_message WHERE conversation_id IN "
                "(SELECT id FROM conversation WHERE user_id = :uid))"
            ),
            {"uid": _USER_ID},
        )
        await cleanup_session.execute(
            text(
                "DELETE FROM chat_turn_failure WHERE conversation_id IN "
                "(SELECT id FROM conversation WHERE user_id = :uid)"
            ),
            {"uid": _USER_ID},
        )
        await cleanup_session.execute(
            text(
                "DELETE FROM chat_message WHERE conversation_id IN "
                "(SELECT id FROM conversation WHERE user_id = :uid)"
            ),
            {"uid": _USER_ID},
        )
        await cleanup_session.execute(
            text("DELETE FROM conversation WHERE user_id = :uid"), {"uid": _USER_ID}
        )
        await cleanup_session.execute(text('DELETE FROM "user" WHERE id = :uid'), {"uid": _USER_ID})
        await cleanup_session.commit()


async def _create_conversation() -> str:
    async with SessionFactory() as session:
        repo = _SqlAlchemyConversationRepository(session)
        conversation = await repo.get_or_create(uuid4(), _USER_ID, "Task test conversation")
        await session.commit()
        return str(conversation.id)


async def _persist_user_message(conversation_id: str, content: str) -> int:
    # Mimics what `ChatService.persist_user_message` does synchronously in
    # the router before this task is ever enqueued -- the task itself no
    # longer writes the user's message.
    async with SessionFactory() as session:
        repo = _SqlAlchemyChatMessageRepository(session)
        message = await repo.append_message(UUID(conversation_id), role="user", content=content)
        await session.commit()
        return message.id


async def _stream_entries(conversation_id: str) -> list[tuple[str, dict]]:
    raw = await redis_client.xrange(turn_stream_key(conversation_id))
    return [(fields["event_type"], json.loads(fields["payload"])) for _entry_id, fields in raw]


@pytest.mark.asyncio
async def test_generate_chat_reply_task_persists_and_publishes_on_success(monkeypatch):
    monkeypatch.setattr(
        "src.infra.task_queue.chat_tasks.get_openrouter_client",
        lambda: _FakeOpenRouterClient(),
    )
    conversation_id = await _create_conversation()
    user_message_id = await _persist_user_message(conversation_id, "How is the tournament going?")

    await generate_chat_reply_task(
        {}, conversation_id, _USER_ID, "How is the tournament going?", user_message_id
    )

    async with SessionFactory() as session:
        chat_message_repo = _SqlAlchemyChatMessageRepository(session)
        messages = await chat_message_repo.list_for_conversation(UUID(conversation_id), _USER_ID)

    # The task itself only appends the assistant's reply -- the user's
    # message (persisted above via `_persist_user_message`, mimicking the
    # router) is already there.
    assert [(m.role, m.content) for m in messages] == [
        ("user", "How is the tournament going?"),
        ("assistant", _REPLY_CONTENT),
    ]

    entries = await _stream_entries(conversation_id)
    event_types = [event_type for event_type, _payload in entries]
    assert event_types[-1] == "MessageDoneEvent"
    assert "ContentDeltaEvent" in event_types

    assert await redis_client.get(turn_in_progress_key(conversation_id)) is None
    stream_ttl = await redis_client.ttl(turn_stream_key(conversation_id))
    assert stream_ttl > 0


@pytest.mark.asyncio
async def test_generate_chat_reply_task_clears_progress_flag_and_publishes_error_on_failure(
    monkeypatch,
):
    monkeypatch.setattr(
        "src.infra.task_queue.chat_tasks.get_openrouter_client",
        lambda: _FailingOpenRouterClient(),
    )
    conversation_id = await _create_conversation()
    user_message_id = await _persist_user_message(conversation_id, "This will fail")

    with pytest.raises(RuntimeError, match="simulated OpenRouter failure"):
        await generate_chat_reply_task(
            {}, conversation_id, _USER_ID, "This will fail", user_message_id
        )

    entries = await _stream_entries(conversation_id)
    assert entries, "expected at least one error entry published to the stream"
    assert entries[-1][0] not in {"MessageDoneEvent"}

    # The flag must be cleared even though the run failed -- it is not tied
    # to the Postgres session's rollback at all.
    assert await redis_client.get(turn_in_progress_key(conversation_id)) is None

    async with SessionFactory() as session:
        failure_repo = _SqlAlchemyChatTurnFailureRepository(session)
        detail = await failure_repo.get_detail_for_message(user_message_id)
    assert detail is not None
    assert "simulated OpenRouter failure" in detail
