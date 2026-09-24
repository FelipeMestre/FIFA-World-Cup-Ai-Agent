"""Integration tests against a real Postgres instance (no mocking, per
AGENTS.md's testing anti-pattern table): verifies
`_SqlAlchemyConversationRepository`'s get-or-create/ownership/list/title/
touch behavior and its `Conversation` <-> `ConversationSchema` mapping.

`ConversationRepositoryInterface` write methods deliberately never commit
(only flush) -- these tests drive the transaction boundary themselves,
mirroring how the caller (T4's chat endpoint) is expected to own it.
"""

from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.chat.exceptions.chat_exceptions import ConversationOwnershipError
from src.infra.postgres.config import SessionFactory, engine
from src.infra.postgres.repositories.conversation_repository import (
    _SqlAlchemyConversationRepository,
)

_USER_ID = 990301
_OTHER_USER_ID = 990302


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    async with SessionFactory() as session:
        for user_id in (_USER_ID, _OTHER_USER_ID):
            await session.execute(
                text(
                    'INSERT INTO "user" (id, email, name, password_hash, is_admin, created_at) '
                    "VALUES (:id, :email, split_part(:email, '@', 1), 'hash', false, now())"
                ),
                {"id": user_id, "email": f"conversation-repo-test-{user_id}@example.test"},
            )
        await session.commit()
        yield session
    async with SessionFactory() as cleanup_session:
        await cleanup_session.execute(
            text("DELETE FROM conversation WHERE user_id IN (:a, :b)"),
            {"a": _USER_ID, "b": _OTHER_USER_ID},
        )
        await cleanup_session.execute(
            text('DELETE FROM "user" WHERE id IN (:a, :b)'), {"a": _USER_ID, "b": _OTHER_USER_ID}
        )
        await cleanup_session.commit()
    await engine.dispose()


async def test_get_or_create_creates_a_new_conversation(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyConversationRepository(db_session)
    conversation_id = uuid4()

    created = await repository.get_or_create(conversation_id, _USER_ID, "First message")
    await db_session.commit()

    assert created.id == conversation_id
    assert created.user_id == _USER_ID
    assert created.title == "First message"


async def test_get_or_create_is_idempotent_for_the_same_owner(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyConversationRepository(db_session)
    conversation_id = uuid4()
    first = await repository.get_or_create(conversation_id, _USER_ID, "First message")
    await db_session.commit()

    second = await repository.get_or_create(conversation_id, _USER_ID, "Ignored default title")

    assert second.id == first.id
    assert second.title == "First message"


async def test_get_or_create_raises_when_id_owned_by_a_different_user(
    db_session: AsyncSession,
) -> None:
    repository = _SqlAlchemyConversationRepository(db_session)
    conversation_id = uuid4()
    await repository.get_or_create(conversation_id, _USER_ID, "First message")
    await db_session.commit()

    with pytest.raises(ConversationOwnershipError):
        await repository.get_or_create(conversation_id, _OTHER_USER_ID, "Someone else's title")


async def test_get_owned_returns_none_for_unknown_id(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyConversationRepository(db_session)

    assert await repository.get_owned(uuid4(), _USER_ID) is None


async def test_get_owned_returns_none_for_a_conversation_owned_by_another_user(
    db_session: AsyncSession,
) -> None:
    repository = _SqlAlchemyConversationRepository(db_session)
    conversation_id = uuid4()
    await repository.get_or_create(conversation_id, _USER_ID, "First message")
    await db_session.commit()

    assert await repository.get_owned(conversation_id, _OTHER_USER_ID) is None


async def test_get_owned_returns_the_conversation_for_its_owner(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyConversationRepository(db_session)
    conversation_id = uuid4()
    await repository.get_or_create(conversation_id, _USER_ID, "First message")
    await db_session.commit()

    found = await repository.get_owned(conversation_id, _USER_ID)

    assert found is not None
    assert found.id == conversation_id


async def test_list_for_user_orders_by_updated_at_desc(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyConversationRepository(db_session)
    older_id = uuid4()
    newer_id = uuid4()
    await repository.get_or_create(older_id, _USER_ID, "Older conversation")
    await db_session.commit()
    await repository.get_or_create(newer_id, _USER_ID, "Newer conversation")
    await db_session.commit()
    await repository.touch(newer_id)
    await db_session.commit()

    conversations = await repository.list_for_user(_USER_ID)

    ids_in_order = [c.id for c in conversations]
    assert ids_in_order.index(newer_id) < ids_in_order.index(older_id)


async def test_update_title_updates_and_returns_the_conversation(
    db_session: AsyncSession,
) -> None:
    repository = _SqlAlchemyConversationRepository(db_session)
    conversation_id = uuid4()
    await repository.get_or_create(conversation_id, _USER_ID, "Original title")
    await db_session.commit()

    updated = await repository.update_title(conversation_id, _USER_ID, "Renamed title")
    await db_session.commit()

    assert updated is not None
    assert updated.title == "Renamed title"
    reloaded = await repository.get_owned(conversation_id, _USER_ID)
    assert reloaded is not None
    assert reloaded.title == "Renamed title"


async def test_update_title_returns_none_when_not_owned(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyConversationRepository(db_session)
    conversation_id = uuid4()
    await repository.get_or_create(conversation_id, _USER_ID, "Original title")
    await db_session.commit()

    result = await repository.update_title(conversation_id, _OTHER_USER_ID, "Hijacked title")

    assert result is None


async def test_touch_advances_updated_at(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyConversationRepository(db_session)
    conversation_id = uuid4()
    created = await repository.get_or_create(conversation_id, _USER_ID, "First message")
    await db_session.commit()

    await repository.touch(conversation_id)
    await db_session.commit()

    touched = await repository.get_owned(conversation_id, _USER_ID)
    assert touched is not None
    assert touched.updated_at >= created.updated_at
