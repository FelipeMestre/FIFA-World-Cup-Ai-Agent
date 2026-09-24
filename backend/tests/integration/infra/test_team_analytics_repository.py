"""Integration tests against a real Postgres instance (no mocking, per
AGENTS.md's testing anti-pattern table): verifies
`_SqlAlchemyTeamAnalyticsRepository.get_team_analysis`'s aggregation across
`national_team`, `match`, `match_team_stat`, and `match_event`.
"""

from collections.abc import AsyncGenerator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.infra.postgres.config import SessionFactory, engine
from src.infra.postgres.repositories.team_analytics_repository import (
    _SqlAlchemyTeamAnalyticsRepository,
)

_TEAM_ID = 990401
_OPPONENT_ID = 990402
_STAGE_ID = 990401
_VENUE_ID = 990401
_REFEREE_ID = 990401
_PLAYER_ID = 990401
_MATCH_ID = 990401


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    async with SessionFactory() as session:
        await session.execute(
            text(
                "INSERT INTO national_team (team_id, team_name, fifa_code, confederation) "
                "VALUES (:id, 'Test Team A', 'TTA', 'UEFA')"
            ),
            {"id": _TEAM_ID},
        )
        await session.execute(
            text(
                "INSERT INTO national_team (team_id, team_name, confederation) "
                "VALUES (:id, 'Test Team B', 'CONMEBOL')"
            ),
            {"id": _OPPONENT_ID},
        )
        await session.execute(
            text(
                "INSERT INTO tournament_stage (stage_id, stage_name, is_knockout) "
                "VALUES (:id, 'Group Stage', false)"
            ),
            {"id": _STAGE_ID},
        )
        await session.execute(
            text(
                "INSERT INTO venue (venue_id, stadium_name, city, country, capacity, "
                "latitude, longitude, elevation_meters) "
                "VALUES (:id, 'Test Stadium', 'Test City', 'Test Country', 50000, "
                "0.0, 0.0, 0)"
            ),
            {"id": _VENUE_ID},
        )
        await session.execute(
            text(
                "INSERT INTO referee (referee_id, name, country, avg_cards_per_game) "
                "VALUES (:id, 'Test Referee', 'Test Country', 3.5)"
            ),
            {"id": _REFEREE_ID},
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
                "INSERT INTO match (match_id, date, kickoff_time_utc, stage_id, venue_id, "
                "home_team_id, away_team_id, home_score, away_score, status, result_type, "
                "home_xg, away_xg, referee_id, player_of_the_match_id) "
                "VALUES (:id, '2026-06-15', '18:00:00', :stage_id, :venue_id, "
                ":home_id, :away_id, 2, 1, 'completed', 'regulation', "
                "1.5, 1.0, :referee_id, :player_id)"
            ),
            {
                "id": _MATCH_ID,
                "stage_id": _STAGE_ID,
                "venue_id": _VENUE_ID,
                "home_id": _TEAM_ID,
                "away_id": _OPPONENT_ID,
                "referee_id": _REFEREE_ID,
                "player_id": _PLAYER_ID,
            },
        )
        await session.execute(
            text(
                "INSERT INTO match_team_stat (match_id, team_id, possession_pct, total_shots, "
                "shots_on_target, corners, fouls, offsides, saves, data_source, last_updated) "
                "VALUES (:match_id, :team_id, 60, 14, 6, 7, 9, 1, 4, 'test', now())"
            ),
            {"match_id": _MATCH_ID, "team_id": _TEAM_ID},
        )
        await session.execute(
            text(
                "INSERT INTO match_team_stat (match_id, team_id, possession_pct, total_shots, "
                "shots_on_target, corners, fouls, offsides, saves, data_source, last_updated) "
                "VALUES (:match_id, :team_id, 40, 8, 3, 3, 11, 2, 3, 'test', now())"
            ),
            {"match_id": _MATCH_ID, "team_id": _OPPONENT_ID},
        )
        await session.execute(
            text(
                "INSERT INTO match_event (event_id, match_id, minute, event_type, team_id, "
                "player_id) VALUES (:id, :match_id, 55, 'Yellow Card', :team_id, :player_id)"
            ),
            {"id": _MATCH_ID, "match_id": _MATCH_ID, "team_id": _TEAM_ID, "player_id": _PLAYER_ID},
        )
        await session.commit()
        yield session
    async with SessionFactory() as cleanup_session:
        await cleanup_session.execute(
            text("DELETE FROM match_event WHERE match_id = :id"), {"id": _MATCH_ID}
        )
        await cleanup_session.execute(
            text("DELETE FROM match_team_stat WHERE match_id = :id"), {"id": _MATCH_ID}
        )
        await cleanup_session.execute(
            text("DELETE FROM match WHERE match_id = :id"), {"id": _MATCH_ID}
        )
        await cleanup_session.execute(
            text("DELETE FROM player WHERE player_id = :id"), {"id": _PLAYER_ID}
        )
        await cleanup_session.execute(
            text("DELETE FROM referee WHERE referee_id = :id"), {"id": _REFEREE_ID}
        )
        await cleanup_session.execute(
            text("DELETE FROM venue WHERE venue_id = :id"), {"id": _VENUE_ID}
        )
        await cleanup_session.execute(
            text("DELETE FROM tournament_stage WHERE stage_id = :id"), {"id": _STAGE_ID}
        )
        await cleanup_session.execute(
            text("DELETE FROM national_team WHERE team_id IN (:id, :opponent_id)"),
            {"id": _TEAM_ID, "opponent_id": _OPPONENT_ID},
        )
        await cleanup_session.commit()
    await engine.dispose()


async def test_get_team_analysis_returns_none_for_unmatched_team(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyTeamAnalyticsRepository(db_session)
    analysis = await repository.get_team_analysis("No Such Country")
    assert analysis is None


async def test_get_team_analysis_resolves_by_exact_name(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyTeamAnalyticsRepository(db_session)
    analysis = await repository.get_team_analysis("Test Team A")

    assert analysis is not None
    assert analysis.id == str(_TEAM_ID)
    assert analysis.code == "TTA"
    assert analysis.name == "Test Team A"


async def test_get_team_analysis_resolves_by_fifa_code(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyTeamAnalyticsRepository(db_session)
    analysis = await repository.get_team_analysis("TTA")
    assert analysis is not None
    assert analysis.id == str(_TEAM_ID)


async def test_get_team_analysis_resolves_by_fuzzy_substring(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyTeamAnalyticsRepository(db_session)
    analysis = await repository.get_team_analysis("Team A")
    assert analysis is not None
    assert analysis.id == str(_TEAM_ID)


async def test_get_team_analysis_derives_win_from_scoreline(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyTeamAnalyticsRepository(db_session)
    analysis = await repository.get_team_analysis("Test Team A")

    assert analysis is not None
    assert analysis.record.won == 1
    assert analysis.record.drawn == 0
    assert analysis.record.lost == 0
    assert analysis.record.goals_for == 2
    assert analysis.record.goals_against == 1
    assert analysis.goal_difference == 1
    assert analysis.clean_sheets == 0
    assert analysis.conceded_per_game == 1.0
    assert analysis.scope_label == "WC 2026 · 1 matches"


async def test_get_team_analysis_lists_the_match_and_opponent(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyTeamAnalyticsRepository(db_session)
    analysis = await repository.get_team_analysis("Test Team A")

    assert analysis is not None
    assert len(analysis.match_results) == 1
    match_result = analysis.match_results[0]
    assert match_result.stage == "Group Stage"
    assert match_result.opponent_code == "TES"  # opponent has no fifa_code -> fallback
    assert match_result.opponent_name == "Test Team B"
    assert match_result.score == "2–1"
    assert match_result.result == "W"

    assert len(analysis.goals_by_match) == 1
    assert analysis.goals_by_match[0].goals_for == 2
    assert analysis.goals_by_match[0].goals_against == 1


async def test_get_team_analysis_compares_stats_against_the_field(db_session: AsyncSession) -> None:
    """`field_value` is a tournament-wide average across every team's every
    match -- this shared dev DB is not test-isolated (other tests/fixtures
    leave rows behind), so this only asserts internal consistency: this
    team's own value, and that `field_value`/`delta` agree with an
    independently-computed average over the real table contents.
    """
    repository = _SqlAlchemyTeamAnalyticsRepository(db_session)
    analysis = await repository.get_team_analysis("Test Team A")

    assert analysis is not None
    possession_row = next(row for row in analysis.tournament_averages if row.label == "Possession")
    assert possession_row.value == "60.0%"

    field_avg_result = await db_session.execute(
        text("SELECT AVG(possession_pct) FROM match_team_stat")
    )
    field_avg = float(field_avg_result.scalar_one())
    assert possession_row.field_value == f"{field_avg:.1f}%"
    expected_delta = 60.0 - field_avg
    glyph = "▲" if expected_delta >= 0 else "▼"
    assert possession_row.delta == f"{glyph} {abs(expected_delta):.1f}"


async def test_get_team_analysis_counts_discipline(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyTeamAnalyticsRepository(db_session)
    analysis = await repository.get_team_analysis("Test Team A")

    assert analysis is not None
    assert analysis.discipline.yellow_cards == 1
    assert analysis.discipline.red_cards == 0
    assert analysis.discipline.fouls == 9
    assert analysis.discipline.yellow_per_match == 1.0
