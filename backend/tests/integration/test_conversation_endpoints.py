"""Integration tests for the `/api/v1/conversations` router (T5):
`GET /conversations` (sidebar list), `PATCH /conversations/{id}` (title
rename), `GET /conversations/{id}/messages` (full replay). Uses real
Postgres (no mocking, per AGENTS.md's testing anti-pattern table) and
`app.dependency_overrides` for auth, mirroring
`test_chat_send_message.py`'s conventions.
"""

from collections.abc import AsyncGenerator
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from src.api.v1.auth.services.dependencies import parse_jwt_data
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
from src.infra.task_queue.chat_tasks import turn_in_progress_key
from src.main import app

_USER_ID = 990701
_OTHER_USER_ID = 990702


@pytest.fixture(autouse=True)
async def _seed_users() -> AsyncGenerator[None]:
    async with SessionFactory() as session:
        for user_id in (_USER_ID, _OTHER_USER_ID):
            await session.execute(
                text(
                    'INSERT INTO "user" (id, email, password_hash, is_admin, created_at) '
                    "VALUES (:id, :email, 'hash', false, now())"
                ),
                {"id": user_id, "email": f"conversation-endpoints-test-{user_id}@example.test"},
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
                "DELETE FROM chat_turn_failure WHERE conversation_id IN "
                "(SELECT id FROM conversation WHERE user_id IN (:a, :b))"
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


async def _create_conversation(user_id: int, title: str) -> Any:
    async with SessionFactory() as session:
        repo = _SqlAlchemyConversationRepository(session)
        conversation = await repo.get_or_create(uuid4(), user_id, title)
        await session.commit()
        return conversation


@pytest.mark.asyncio
async def test_list_conversations_returns_only_current_users_conversations_in_activity_order(
    client: AsyncClient,
) -> None:
    older = await _create_conversation(_USER_ID, "Older conversation")
    newer = await _create_conversation(_USER_ID, "Newer conversation")
    await _create_conversation(_OTHER_USER_ID, "Someone else's conversation")

    async with SessionFactory() as session:
        repo = _SqlAlchemyConversationRepository(session)
        await repo.touch(older.id)
        await session.commit()

    response = await client.get(
        "/api/v1/conversations", headers={"Authorization": "Bearer test-token"}
    )

    assert response.status_code == 200
    body = response.json()
    ids = [item["id"] for item in body]
    assert str(older.id) in ids
    assert str(newer.id) in ids
    assert str(older.id) == ids[0]
    titles = {item["id"]: item["title"] for item in body}
    assert titles[str(older.id)] == "Older conversation"


@pytest.mark.asyncio
async def test_update_conversation_title_renames_and_returns_summary(
    client: AsyncClient,
) -> None:
    conversation = await _create_conversation(_USER_ID, "Original title")

    response = await client.patch(
        f"/api/v1/conversations/{conversation.id}",
        json={"title": "Renamed title"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(conversation.id)
    assert body["title"] == "Renamed title"

    async with SessionFactory() as session:
        repo = _SqlAlchemyConversationRepository(session)
        persisted = await repo.get_owned(conversation.id, _USER_ID)
    assert persisted is not None
    assert persisted.title == "Renamed title"


@pytest.mark.asyncio
async def test_update_conversation_title_404_for_another_users_conversation(
    client: AsyncClient,
) -> None:
    conversation = await _create_conversation(_OTHER_USER_ID, "Not yours")

    response = await client.patch(
        f"/api/v1/conversations/{conversation.id}",
        json={"title": "Hijacked title"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_conversation_title_404_for_nonexistent_conversation_same_as_not_owned(
    client: AsyncClient,
) -> None:
    not_owned = await _create_conversation(_OTHER_USER_ID, "Not yours")

    missing_response = await client.patch(
        f"/api/v1/conversations/{uuid4()}",
        json={"title": "New title"},
        headers={"Authorization": "Bearer test-token"},
    )
    not_owned_response = await client.patch(
        f"/api/v1/conversations/{not_owned.id}",
        json={"title": "New title"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert missing_response.status_code == 404
    assert not_owned_response.status_code == 404
    assert missing_response.json() == not_owned_response.json()


@pytest.mark.asyncio
async def test_get_conversation_messages_returns_ordered_parts_including_a_widget(
    client: AsyncClient,
) -> None:
    conversation = await _create_conversation(_USER_ID, "Widget conversation")

    async with SessionFactory() as session:
        chat_message_repo = _SqlAlchemyChatMessageRepository(session)
        await chat_message_repo.append_message(conversation.id, "user", "How is Test Team doing?")
        await chat_message_repo.append_message(
            conversation.id,
            "assistant",
            "Here's how they did.",
            widgets=[("get_team_analysis", "team_widget", {"id": "1", "name": "Test Team"})],
        )
        await session.commit()

    response = await client.get(
        f"/api/v1/conversations/{conversation.id}/messages",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["conversation_id"] == str(conversation.id)
    assert body["title"] == "Widget conversation"
    assert [m["role"] for m in body["messages"]] == ["user", "assistant"]
    assert body["messages"][0]["parts"] == [{"type": "text", "content": "How is Test Team doing?"}]
    assert body["messages"][1]["parts"] == [
        {"type": "team_widget", "data": {"id": "1", "name": "Test Team"}},
        {"type": "text", "content": "Here's how they did."},
    ]


@pytest.mark.asyncio
async def test_get_conversation_messages_404_for_another_users_conversation(
    client: AsyncClient,
) -> None:
    conversation = await _create_conversation(_OTHER_USER_ID, "Not yours")
    async with SessionFactory() as session:
        chat_message_repo = _SqlAlchemyChatMessageRepository(session)
        await chat_message_repo.append_message(conversation.id, "user", "Secret message")
        await session.commit()

    response = await client.get(
        f"/api/v1/conversations/{conversation.id}/messages",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_conversations_reports_is_generating_from_the_redis_flag(
    client: AsyncClient,
) -> None:
    generating = await _create_conversation(_USER_ID, "Generating")
    idle = await _create_conversation(_USER_ID, "Idle")
    await redis_client.set(turn_in_progress_key(str(generating.id)), "1", ex=60)

    response = await client.get(
        "/api/v1/conversations", headers={"Authorization": "Bearer test-token"}
    )

    assert response.status_code == 200
    flags = {item["id"]: item["is_generating"] for item in response.json()}
    assert flags[str(generating.id)] is True
    assert flags[str(idle.id)] is False

    await redis_client.delete(turn_in_progress_key(str(generating.id)))


@pytest.mark.asyncio
async def test_get_conversation_messages_surfaces_failure_only_on_the_last_message(
    client: AsyncClient,
) -> None:
    conversation = await _create_conversation(_USER_ID, "Failed turn")

    async with SessionFactory() as session:
        chat_message_repo = _SqlAlchemyChatMessageRepository(session)
        failed_user_message = await chat_message_repo.append_message(
            conversation.id, "user", "This one failed"
        )
        await session.commit()

    async with SessionFactory() as session:
        failure_repo = _SqlAlchemyChatTurnFailureRepository(session)
        await failure_repo.record_failure(
            conversation.id, failed_user_message.id, "The chat assistant is unavailable"
        )

    stale_response = await client.get(
        f"/api/v1/conversations/{conversation.id}/messages",
        headers={"Authorization": "Bearer test-token"},
    )
    assert stale_response.json()["last_turn_failure"] == "The chat assistant is unavailable"

    # A retry appends a new user message -- the old failure is now stale
    # and must no longer be surfaced, even though its row still exists.
    async with SessionFactory() as session:
        chat_message_repo = _SqlAlchemyChatMessageRepository(session)
        await chat_message_repo.append_message(conversation.id, "user", "Retrying")
        await session.commit()

    retried_response = await client.get(
        f"/api/v1/conversations/{conversation.id}/messages",
        headers={"Authorization": "Bearer test-token"},
    )
    assert retried_response.json()["last_turn_failure"] is None
