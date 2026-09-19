"""Integration tests against a real Postgres instance (no mocking, per
AGENTS.md's testing anti-pattern table): verifies
`PlayerIdentityLinkRepository`'s point-read/update paths and its
`upsert_candidates` composition on top of the generic ingestion repository.
"""

from collections.abc import AsyncGenerator
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.ingestion.exceptions.ingestion_exceptions import IdentityLinkNotFoundError
from src.domain.ingestion.model.player_identity_candidate import PlayerIdentityCandidate
from src.domain.ingestion.model.player_identity_link import LinkReviewStatus, PlayerMatchMethod
from src.infra.postgres.config import SessionFactory, engine
from src.infra.postgres.repositories.player_identity_link_repository import (
    _SqlAlchemyPlayerIdentityLinkRepository,
)

_TEAM_ID = 990201
_PLAYER_ID = 990201
_OTHER_PLAYER_ID = 990202
_REAL_PLAYER_ID = 990201
_USER_ID = 990201


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    async with SessionFactory() as session:
        await session.execute(
            text(
                "INSERT INTO team (team_id, team_name, fifa_code, group_letter, confederation, "
                "fifa_ranking_pre_tournament, elo_rating, manager_name) "
                "VALUES (:id, 'Test Team', 'TST', 'A', 'UEFA', 1, 1000, 'Test Manager')"
            ),
            {"id": _TEAM_ID},
        )
        await session.execute(
            text(
                "INSERT INTO player (player_id, team_id, player_name, position, club_team, "
                "market_value_eur, caps, date_of_birth, height_cm, goals) "
                "VALUES (:id, :team_id, 'Test Player', 'FW', 'Test Club', 1000000, 10, "
                "'2000-01-01', 180, 5)"
            ),
            {"id": _PLAYER_ID, "team_id": _TEAM_ID},
        )
        await session.execute(
            text(
                "INSERT INTO player (player_id, team_id, player_name, position, club_team, "
                "market_value_eur, caps, date_of_birth, height_cm, goals) "
                "VALUES (:id, :team_id, 'Other Player', 'FW', 'Test Club', 1000000, 10, "
                "'2000-01-01', 180, 5)"
            ),
            {"id": _OTHER_PLAYER_ID, "team_id": _TEAM_ID},
        )
        await session.execute(
            text(
                "INSERT INTO real_player (player_id, first_name, last_name, position, "
                "profile_url, last_synced_at) "
                "VALUES (:id, 'Real', 'Player', 'Forward', 'https://example.test/player', now())"
            ),
            {"id": _REAL_PLAYER_ID},
        )
        await session.execute(
            text(
                'INSERT INTO "user" (id, email, password_hash, is_admin, created_at) '
                "VALUES (:id, :email, 'hash', true, now())"
            ),
            {"id": _USER_ID, "email": f"identity-link-test-{_USER_ID}@example.test"},
        )
        await session.commit()
        yield session
    async with SessionFactory() as cleanup_session:
        await cleanup_session.execute(
            text("DELETE FROM player_identity_link WHERE player_id IN (:id, :other_id)"),
            {"id": _PLAYER_ID, "other_id": _OTHER_PLAYER_ID},
        )
        await cleanup_session.execute(
            text("DELETE FROM player WHERE player_id IN (:id, :other_id)"),
            {"id": _PLAYER_ID, "other_id": _OTHER_PLAYER_ID},
        )
        await cleanup_session.execute(
            text("DELETE FROM team WHERE team_id = :id"), {"id": _TEAM_ID}
        )
        await cleanup_session.execute(
            text("DELETE FROM real_player WHERE player_id = :id"), {"id": _REAL_PLAYER_ID}
        )
        await cleanup_session.execute(text('DELETE FROM "user" WHERE id = :id'), {"id": _USER_ID})
        await cleanup_session.commit()
    await engine.dispose()


async def _link_id_for_player(session: AsyncSession, player_id: int) -> int:
    result = await session.execute(
        text("SELECT id FROM player_identity_link WHERE player_id = :player_id"),
        {"player_id": player_id},
    )
    return result.scalar_one()


async def test_upsert_candidates_auto_approves_high_confidence(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyPlayerIdentityLinkRepository(db_session)
    candidate = PlayerIdentityCandidate(
        player_id=_PLAYER_ID,
        real_player_id=_REAL_PLAYER_ID,
        match_method=PlayerMatchMethod.EXACT_NAME_DOB,
        match_confidence=Decimal("1.000"),
    )

    result = await repository.upsert_candidates([candidate])

    assert result.row_count == 1
    link_id = await _link_id_for_player(db_session, _PLAYER_ID)
    link = await repository.get(link_id)
    assert link is not None
    assert link.status == LinkReviewStatus.APPROVED
    assert link.reviewed_by_user_id is None


async def test_upsert_candidates_queues_fuzzy_matches_as_pending(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyPlayerIdentityLinkRepository(db_session)
    candidate = PlayerIdentityCandidate(
        player_id=_PLAYER_ID,
        real_player_id=_REAL_PLAYER_ID,
        match_method=PlayerMatchMethod.FUZZY_NAME,
        match_confidence=Decimal("0.870"),
    )

    await repository.upsert_candidates([candidate])

    pending_links = await repository.list_pending()
    assert any(link.player_id == _PLAYER_ID for link in pending_links)


async def test_update_status_approves_and_records_reviewer(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyPlayerIdentityLinkRepository(db_session)
    candidate = PlayerIdentityCandidate(
        player_id=_PLAYER_ID,
        real_player_id=_REAL_PLAYER_ID,
        match_method=PlayerMatchMethod.FUZZY_NAME,
        match_confidence=Decimal("0.870"),
    )
    await repository.upsert_candidates([candidate])
    link_id = await _link_id_for_player(db_session, _PLAYER_ID)

    approved = await repository.update_status(link_id, LinkReviewStatus.APPROVED, _USER_ID)

    assert approved.status == LinkReviewStatus.APPROVED
    assert approved.reviewed_by_user_id == _USER_ID


async def test_upsert_candidates_keeps_highest_confidence_on_real_player_id_collision(
    db_session: AsyncSession,
) -> None:
    # Reproduces a real bug hit against the live Transfermarkt source: two
    # different synthetic players both matched to the same real_player_id.
    # real_player_id is unique, and a same-batch collision on it (not the
    # ON CONFLICT (player_id) target) would raise UniqueViolationError
    # without the dedup in upsert_candidates.
    repository = _SqlAlchemyPlayerIdentityLinkRepository(db_session)
    weaker = PlayerIdentityCandidate(
        player_id=_OTHER_PLAYER_ID,
        real_player_id=_REAL_PLAYER_ID,
        match_method=PlayerMatchMethod.FUZZY_NAME,
        match_confidence=Decimal("0.870"),
    )
    stronger = PlayerIdentityCandidate(
        player_id=_PLAYER_ID,
        real_player_id=_REAL_PLAYER_ID,
        match_method=PlayerMatchMethod.EXACT_NAME_DOB,
        match_confidence=Decimal("1.000"),
    )

    result = await repository.upsert_candidates([weaker, stronger])

    assert result.row_count == 1
    persisted = await db_session.execute(
        text("SELECT player_id FROM player_identity_link WHERE real_player_id = :id"),
        {"id": _REAL_PLAYER_ID},
    )
    assert persisted.scalar_one() == _PLAYER_ID


async def test_update_status_on_unknown_id_raises(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyPlayerIdentityLinkRepository(db_session)

    with pytest.raises(IdentityLinkNotFoundError):
        await repository.update_status(-1, LinkReviewStatus.APPROVED, _USER_ID)
