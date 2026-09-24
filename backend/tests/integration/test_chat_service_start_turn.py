"""Integration tests for `ChatService.start_turn`'s enqueue-on-create
behavior. Runs against real Postgres per AGENTS.md's testing convention;
the only substitution is `enqueue_categorize_conversation` itself (a spy),
since the categorization job's own behavior is already covered end-to-end
by `test_categorize_conversation_task.py` and does not need a real Arq
worker running here.
"""

from uuid import uuid4

import pytest
from sqlalchemy import text

from src.domain.chat.services.chat_service import ChatService
from src.infra.postgres.config import SessionFactory
from src.infra.postgres.repositories.chat_message_repository import get_chat_message_repository
from src.infra.postgres.repositories.conversation_repository import get_conversation_repository

_USER_ID = 990841


@pytest.fixture(autouse=True)
async def _seed_user_and_cleanup():
    async with SessionFactory() as session:
        # `name` is passed as its own bound parameter rather than derived
        # in SQL from a reused `:email` -- see the identical note in
        # `test_categorize_conversation_task.py` for why.
        await session.execute(
            text(
                'INSERT INTO "user" (id, email, name, password_hash, is_admin, created_at) '
                "VALUES (:id, :email, :name, 'hash', false, now())"
            ),
            {
                "id": _USER_ID,
                "email": f"start-turn-test-{_USER_ID}@example.test",
                "name": f"start-turn-test-{_USER_ID}",
            },
        )
        await session.commit()
    yield
    async with SessionFactory() as cleanup_session:
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


@pytest.mark.asyncio
async def test_start_turn_enqueues_categorization_only_on_first_call(monkeypatch):
    calls: list[tuple[str, int, str]] = []

    async def _fake_enqueue(conversation_id: str, user_id: int, first_message: str) -> None:
        calls.append((conversation_id, user_id, first_message))

    monkeypatch.setattr(
        "src.domain.chat.services.chat_service.enqueue_categorize_conversation",
        _fake_enqueue,
    )

    conversation_id = uuid4()
    async with SessionFactory() as session:
        chat_service = ChatService(
            conversation_cache=None,
            openrouter_client=None,
            tool_registry={},
            conversation_repo=get_conversation_repository(session),
            chat_message_repo=get_chat_message_repository(session),
            session=session,
        )
        await chat_service.start_turn(
            conversation_id=conversation_id, user_id=_USER_ID, first_message="First message"
        )
        # Second call for the SAME conversation -- it already exists now, so
        # `created` is False and the job must not be enqueued again.
        await chat_service.start_turn(
            conversation_id=conversation_id, user_id=_USER_ID, first_message="Second message"
        )

    assert calls == [(str(conversation_id), _USER_ID, "First message")]
