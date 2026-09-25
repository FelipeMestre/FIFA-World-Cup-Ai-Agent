"""Integration tests against a real Postgres instance (no mocking, per
AGENTS.md's testing anti-pattern table): verifies `RealPlayerRepository`'s
`search` -- the lookup the admin "correct match" flow uses to find the
intended Transfermarkt player by name -- and `list_match_candidates`, which
feeds `PlayerIdentityMatchingService.match()` for the identity-link rematch
feature.
"""

from collections.abc import AsyncGenerator
from datetime import date

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
                "INSERT INTO real_player (player_id, first_name, last_name, "
                "date_of_birth, height_cm, position, profile_url, last_synced_at) "
                "VALUES (:id, 'Kylian', 'Mbappe', '1998-12-20', 178, 'Forward', "
                "'https://example.test/mbappe', now())"
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


async def test_list_match_candidates_shapes_rows_for_the_matching_service(
    db_session: AsyncSession,
) -> None:
    # PlayerIdentityMatchingService.match() reads these exact dict keys --
    # in particular `height_in_cm`, which does NOT match the persisted
    # `height_cm` column name, and a `date`-typed `date_of_birth`, not a
    # string. Getting either wrong makes matching silently return wrong/no
    # results (see that service's own docstring on this exact class of bug).
    repository = _SqlAlchemyRealPlayerRepository(db_session)

    candidates = await repository.list_match_candidates()

    mbappe = next(c for c in candidates if c["player_id"] == _PLAYER_ID)
    assert mbappe["first_name"] == "Kylian"
    assert mbappe["last_name"] == "Mbappe"
    assert mbappe["date_of_birth"] == date(1998, 12, 20)
    assert mbappe["height_in_cm"] == 178
    assert mbappe["current_national_team_id"] is None

    other = next(c for c in candidates if c["player_id"] == _OTHER_PLAYER_ID)
    assert other["date_of_birth"] is None
    assert other["height_in_cm"] is None
