"""Integration tests against a real Postgres instance (no mocking, per
AGENTS.md's testing anti-pattern table): verifies `RealPlayerRepository`'s
`search` -- the lookup the admin "correct match" flow uses to find the
intended Transfermarkt player by name.
"""

from collections.abc import AsyncGenerator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.infra.postgres.config import SessionFactory, engine
from src.infra.postgres.repositories.real_player_repository import (
    _SqlAlchemyRealPlayerRepository,
)

_PLAYER_ID = 990401
_OTHER_PLAYER_ID = 990402


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    async with SessionFactory() as session:
        await session.execute(
            text(
                "INSERT INTO real_player (player_id, first_name, last_name, position, "
                "profile_url, last_synced_at) "
                "VALUES (:id, 'Kylian', 'Mbappe', 'Forward', 'https://example.test/mbappe', now())"
            ),
            {"id": _PLAYER_ID},
        )
        await session.execute(
            text(
                "INSERT INTO real_player (player_id, first_name, last_name, position, "
                "profile_url, last_synced_at) "
                "VALUES (:id, 'Someone', 'Else', 'Midfield', 'https://example.test/else', now())"
            ),
            {"id": _OTHER_PLAYER_ID},
        )
        await session.commit()
        yield session
    async with SessionFactory() as cleanup_session:
        await cleanup_session.execute(
            text("DELETE FROM real_player WHERE player_id IN (:id, :other_id)"),
            {"id": _PLAYER_ID, "other_id": _OTHER_PLAYER_ID},
        )
        await cleanup_session.commit()
    await engine.dispose()


async def test_search_matches_by_partial_name_case_insensitively(
    db_session: AsyncSession,
) -> None:
    repository = _SqlAlchemyRealPlayerRepository(db_session)

    results = await repository.search("mbap")

    assert [player.player_id for player in results] == [_PLAYER_ID]
    assert results[0].first_name == "Kylian"
    assert results[0].last_name == "Mbappe"


async def test_search_matches_across_first_and_last_name(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyRealPlayerRepository(db_session)

    results = await repository.search("Kylian Mbappe")

    assert [player.player_id for player in results] == [_PLAYER_ID]


async def test_search_returns_empty_for_no_match(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyRealPlayerRepository(db_session)

    results = await repository.search("Nobody Matching")

    assert results == []


async def test_get_returns_none_for_unknown_id(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyRealPlayerRepository(db_session)

    result = await repository.get(-1)

    assert result is None
