"""Integration test for `POST /api/v1/chat/messages`.

Generation itself moved to a background job (`generate_chat_reply_task`,
covered by `test_generate_chat_reply_task.py`) -- this endpoint's own job is
now just: ownership check, persist the user's message synchronously, reserve
the one-turn-per-conversation guard, and enqueue. No worker runs here, so
these tests never see an assistant reply; they prove the synchronous half of
the contract per AGENTS.md's testing guidance (real Postgres/Redis, no
mocking).
"""

from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from src.api.v1.auth.services.dependencies import parse_jwt_data
from src.infra.postgres.config import SessionFactory
from src.infra.postgres.repositories.chat_message_repository import (
    _SqlAlchemyChatMessageRepository,
)
from src.infra.redis.config import redis_client
from src.infra.task_queue.chat_tasks import turn_in_progress_key
from src.main import app

_USER_ID = 990601
_OTHER_USER_ID = 990602


@pytest.fixture(autouse=True)
async def _seed_chat_users() -> AsyncGenerator[None]:
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
def _override_auth() -> AsyncGenerator[None]:
    def fake_jwt_data() -> dict[str, Any]:
        return {"sub": str(_USER_ID), "is_admin": False}

    app.dependency_overrides[parse_jwt_data] = fake_jwt_data
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_send_message_persists_user_message_and_returns_ack(client: AsyncClient) -> None:
    conversation_id = str(uuid4())
    response = await client.post(
        "/api/v1/chat/messages",
        json={
            "conversation_id": conversation_id,
            "message": "When does the 2026 World Cup group stage run?",
        },
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["conversation_id"] == conversation_id
    # Truncated to 40 chars + an ellipsis -- see ChatService._TITLE_MAX_LENGTH.
    assert body["title"] == "When does the 2026 World Cup group stage…"

    async with SessionFactory() as session:
        chat_message_repository = _SqlAlchemyChatMessageRepository(session)
        messages = await chat_message_repository.list_for_conversation(
            UUID(conversation_id), _USER_ID
        )
    assert [(m.sequence, m.role, m.content) for m in messages] == [
        (1, "user", "When does the 2026 World Cup group stage run?"),
    ]

    await redis_client.delete(turn_in_progress_key(conversation_id))


@pytest.mark.asyncio
async def test_send_message_reserves_the_turn_in_progress_flag(client: AsyncClient) -> None:
    conversation_id = str(uuid4())

    await client.post(
        "/api/v1/chat/messages",
        json={"conversation_id": conversation_id, "message": "First message"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert await redis_client.exists(turn_in_progress_key(conversation_id))

    await redis_client.delete(turn_in_progress_key(conversation_id))


@pytest.mark.asyncio
async def test_send_message_conflicts_when_a_turn_is_already_in_progress(
    client: AsyncClient,
) -> None:
    conversation_id = str(uuid4())
    await redis_client.set(turn_in_progress_key(conversation_id), "1", ex=60)

    response = await client.post(
        "/api/v1/chat/messages",
        json={"conversation_id": conversation_id, "message": "Should be rejected"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 409

    async with SessionFactory() as session:
        chat_message_repository = _SqlAlchemyChatMessageRepository(session)
        messages = await chat_message_repository.list_for_conversation(
            UUID(conversation_id), _USER_ID
        )
    assert messages == []

    await redis_client.delete(turn_in_progress_key(conversation_id))


@pytest.mark.asyncio
async def test_posting_to_another_users_conversation_id_is_forbidden(
    client: AsyncClient,
) -> None:
    conversation_id = str(uuid4())

    owner_response = await client.post(
        "/api/v1/chat/messages",
        json={"conversation_id": conversation_id, "message": "First message"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert owner_response.status_code == 202

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

    await redis_client.delete(turn_in_progress_key(conversation_id))
