"""Integration tests against a real Postgres instance (no mocking, per
AGENTS.md's testing anti-pattern table): verifies
`_SqlAlchemyChatMessageRepository`'s append/sequence/widget/ownership
behavior and its `ChatMessage` <-> `ChatMessageSchema` mapping.

`ChatMessageRepositoryInterface.append_message` deliberately never commits
(only flush) -- these tests drive the transaction boundary themselves,
mirroring how the caller (T4's chat endpoint) is expected to own it.
"""

from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.infra.postgres.config import SessionFactory, engine
from src.infra.postgres.repositories.chat_message_repository import (
    _SqlAlchemyChatMessageRepository,
)
from src.infra.postgres.repositories.conversation_repository import (
    _SqlAlchemyConversationRepository,
)

_USER_ID = 990401
_OTHER_USER_ID = 990402


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    async with SessionFactory() as session:
        for user_id in (_USER_ID, _OTHER_USER_ID):
            await session.execute(
                text(
                    'INSERT INTO "user" (id, email, name, password_hash, is_admin, created_at) '
                    "VALUES (:id, :email, split_part(:email, '@', 1), 'hash', false, now())"
                ),
                {"id": user_id, "email": f"chat-message-repo-test-{user_id}@example.test"},
            )
        await session.commit()
        yield session
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
    await engine.dispose()


async def _seed_conversation(session: AsyncSession, user_id: int = _USER_ID) -> object:
    conversation_repository = _SqlAlchemyConversationRepository(session)
    conversation = await conversation_repository.get_or_create(uuid4(), user_id, "Test chat")
    await session.commit()
    return conversation.id


async def test_append_message_assigns_sequence_one_for_the_first_message(
    db_session: AsyncSession,
) -> None:
    conversation_id = await _seed_conversation(db_session)
    repository = _SqlAlchemyChatMessageRepository(db_session)

    message = await repository.append_message(conversation_id, "user", "Hello there")
    await db_session.commit()

    assert message.sequence == 1
    assert message.role == "user"
    assert message.content == "Hello there"
    assert message.widgets == []


async def test_append_message_increments_sequence_per_conversation(
    db_session: AsyncSession,
) -> None:
    conversation_id = await _seed_conversation(db_session)
    repository = _SqlAlchemyChatMessageRepository(db_session)
    await repository.append_message(conversation_id, "user", "First")
    await db_session.commit()

    second = await repository.append_message(conversation_id, "assistant", "Second")
    await db_session.commit()

    assert second.sequence == 2


async def test_append_message_persists_widgets(db_session: AsyncSession) -> None:
    conversation_id = await _seed_conversation(db_session)
    repository = _SqlAlchemyChatMessageRepository(db_session)

    message = await repository.append_message(
        conversation_id,
        "assistant",
        "Here is a comparison",
        widgets=[("get_player_comparison", "player_comparison", {"players": ["A", "B"]})],
    )
    await db_session.commit()

    assert len(message.widgets) == 1
    widget = message.widgets[0]
    assert widget.tool_name == "get_player_comparison"
    assert widget.widget_type == "player_comparison"
    assert widget.data == {"players": ["A", "B"]}
    assert widget.message_id == message.id


async def test_list_for_conversation_returns_messages_in_sequence_order_with_widgets(
    db_session: AsyncSession,
) -> None:
    conversation_id = await _seed_conversation(db_session)
    repository = _SqlAlchemyChatMessageRepository(db_session)
    await repository.append_message(conversation_id, "user", "First")
    await db_session.commit()
    await repository.append_message(
        conversation_id,
        "assistant",
        "Second",
        widgets=[("get_team_analysis", "team_analysis", {"team": "France"})],
    )
    await db_session.commit()

    messages = await repository.list_for_conversation(conversation_id, _USER_ID)

    assert [m.sequence for m in messages] == [1, 2]
    assert messages[0].content == "First"
    assert messages[0].widgets == []
    assert len(messages[1].widgets) == 1
    assert messages[1].widgets[0].tool_name == "get_team_analysis"


async def test_list_for_conversation_returns_empty_for_a_non_owner(
    db_session: AsyncSession,
) -> None:
    conversation_id = await _seed_conversation(db_session, _USER_ID)
    repository = _SqlAlchemyChatMessageRepository(db_session)
    await repository.append_message(conversation_id, "user", "Secret message")
    await db_session.commit()

    messages = await repository.list_for_conversation(conversation_id, _OTHER_USER_ID)

    assert messages == []


async def test_list_for_conversation_returns_empty_for_unknown_conversation(
    db_session: AsyncSession,
) -> None:
    repository = _SqlAlchemyChatMessageRepository(db_session)

    assert await repository.list_for_conversation(uuid4(), _USER_ID) == []
