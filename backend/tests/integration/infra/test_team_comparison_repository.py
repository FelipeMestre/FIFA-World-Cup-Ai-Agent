"""Integration test for `get_team_comparison` against real Postgres."""

from collections.abc import AsyncGenerator
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.chat.exceptions.chat_exceptions import SameTeamComparisonError, TeamNotFoundError
from src.infra.postgres.config import SessionFactory, engine
from src.infra.postgres.repositories.team_analytics_repository import (
    _SqlAlchemyTeamAnalyticsRepository,
)

_TEAM_A = 990511
_TEAM_B = 990512
_STAGE = 990511
_VENUE = 990511
_REFEREE = 990511
_FORWARD = 990511
_KEEPER = 990512
_OPPONENT_FORWARD = 990513
_MATCH = 990511
_LINEUP_FORWARD = 990511
_LINEUP_KEEPER = 990512
_LINEUP_OPPONENT = 990513
_YELLOW = 990511


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    async with SessionFactory() as session:
        await session.execute(
            text(
                "INSERT INTO national_team (team_id, team_name, fifa_code, confederation, "
                "group_letter, fifa_ranking_pre_tournament, elo_rating, manager_name) "
                "VALUES (:id, 'North Test', 'NTE', 'UEFA', 'A', 4, 1850, 'North Coach')"
            ),
            {"id": _TEAM_A},
        )
        await session.execute(
            text(
                "INSERT INTO national_team (team_id, team_name, fifa_code, confederation, "
                "group_letter, fifa_ranking_pre_tournament, elo_rating, manager_name) "
                "VALUES (:id, 'South Test', 'STE', 'CONMEBOL', 'B', 12, 1720, 'South Coach')"
            ),
            {"id": _TEAM_B},
        )
        await session.execute(
            text(
                "INSERT INTO tournament_stage (stage_id, stage_name, is_knockout) "
                "VALUES (:id, 'Group Stage', false)"
            ),
            {"id": _STAGE},
        )
        await session.execute(
            text(
                "INSERT INTO venue (venue_id, stadium_name, city, country, capacity, "
                "latitude, longitude, elevation_meters) "
                "VALUES (:id, 'Compare Stadium', 'Test City', 'Test Country', 40000, 0, 0, 0)"
            ),
            {"id": _VENUE},
        )
        await session.execute(
            text(
                "INSERT INTO referee (referee_id, name, country, avg_cards_per_game) "
                "VALUES (:id, 'Compare Referee', 'Test Country', 3.0)"
            ),
            {"id": _REFEREE},
        )
        await session.execute(
            text(
                "INSERT INTO player (player_id, team_id, player_name, position, club_team, "
                "market_value_eur, caps, date_of_birth, height_cm, goals) VALUES "
                "(:id, :team_id, :name, :position, :club, :value, :caps, :dob, :height, 0)"
            ),
            [
                {
                    "id": _FORWARD,
                    "team_id": _TEAM_A,
                    "name": "North Forward",
                    "position": "FW",
                    "club": "North Club",
                    "value": 80_000_000,
                    "caps": 30,
                    "dob": date(1998, 3, 1),
                    "height": 182,
                },
                {
                    "id": _KEEPER,
                    "team_id": _TEAM_A,
                    "name": "North Keeper",
                    "position": "GK",
                    "club": "North Club",
                    "value": 20_000_000,
                    "caps": 12,
                    "dob": date(2000, 1, 15),
                    "height": 190,
                },
                {
                    "id": _OPPONENT_FORWARD,
                    "team_id": _TEAM_B,
                    "name": "South Forward",
                    "position": "FW",
                    "club": "South Club",
                    "value": 40_000_000,
                    "caps": 20,
                    "dob": date(2003, 8, 1),
                    "height": 176,
                },
            ],
        )
        await session.execute(
            text(
                "INSERT INTO match (match_id, date, kickoff_time_utc, stage_id, venue_id, "
                "home_team_id, away_team_id, home_score, away_score, status, result_type, "
                "home_xg, away_xg, referee_id, player_of_the_match_id) "
                "VALUES (:id, '2026-06-15', '18:00:00', :stage_id, :venue_id, "
                ":home_id, :away_id, 2, 1, 'completed', 'regulation', "
                "1.8, 0.9, :referee_id, :player_id)"
            ),
            {
                "id": _MATCH,
                "stage_id": _STAGE,
                "venue_id": _VENUE,
                "home_id": _TEAM_A,
                "away_id": _TEAM_B,
                "referee_id": _REFEREE,
                "player_id": _FORWARD,
            },
        )
        await session.execute(
            text(
                "INSERT INTO match_team_stat (match_id, team_id, possession_pct, total_shots, "
                "shots_on_target, corners, fouls, offsides, saves, data_source, last_updated) "
                "VALUES (:match_id, :team_id, :possession, :shots, :on_target, 4, :fouls, 1, "
                ":saves, 'test', '2026-06-16')"
            ),
            [
                {
                    "match_id": _MATCH,
                    "team_id": _TEAM_A,
                    "possession": 62,
                    "shots": 12,
                    "on_target": 5,
                    "fouls": 9,
                    "saves": 2,
                },
                {
                    "match_id": _MATCH,
                    "team_id": _TEAM_B,
                    "possession": 38,
                    "shots": 8,
                    "on_target": 3,
                    "fouls": 14,
                    "saves": 3,
                },
            ],
        )
        await session.execute(
            text(
                "INSERT INTO player_stat (player_id, player_name, team_id, position, "
                "matches_played, matches_started, minutes_played, goals, assists, yellow_cards, "
                "red_cards, penalty_goals, own_goals, clean_sheets, saves, goals_conceded, "
                "last_verified) VALUES (:id, :name, :team_id, :position, 1, 1, 90, :goals, "
                ":assists, 0, 0, 0, 0, :clean_sheets, :saves, :conceded, '2026-06-16')"
            ),
            [
                {
                    "id": _FORWARD,
                    "name": "North Forward",
                    "team_id": _TEAM_A,
                    "position": "FW",
                    "goals": 2,
                    "assists": 1,
                    "clean_sheets": None,
                    "saves": None,
                    "conceded": None,
                },
                {
                    "id": _KEEPER,
                    "name": "North Keeper",
                    "team_id": _TEAM_A,
                    "position": "GK",
                    "goals": 0,
                    "assists": 0,
                    "clean_sheets": 0,
                    "saves": 3,
                    "conceded": 1,
                },
                {
                    "id": _OPPONENT_FORWARD,
                    "name": "South Forward",
                    "team_id": _TEAM_B,
                    "position": "FW",
                    "goals": 1,
                    "assists": 0,
                    "clean_sheets": None,
                    "saves": None,
                    "conceded": None,
                },
            ],
        )
        await session.execute(
            text(
                "INSERT INTO match_lineup (lineup_id, match_id, player_id, team_id, "
                "is_starting_xi, tactical_position, minutes_played) "
                "VALUES (:id, :match_id, :player_id, :team_id, true, :position, 90)"
            ),
            [
                {
                    "id": _LINEUP_FORWARD,
                    "match_id": _MATCH,
                    "player_id": _FORWARD,
                    "team_id": _TEAM_A,
                    "position": "FW",
                },
                {
                    "id": _LINEUP_KEEPER,
                    "match_id": _MATCH,
                    "player_id": _KEEPER,
                    "team_id": _TEAM_A,
                    "position": "GK",
                },
                {
                    "id": _LINEUP_OPPONENT,
                    "match_id": _MATCH,
                    "player_id": _OPPONENT_FORWARD,
                    "team_id": _TEAM_B,
                    "position": "FW",
                },
            ],
        )
        await session.execute(
            text(
                "INSERT INTO match_event (event_id, match_id, minute, event_type, team_id, "
                "player_id) VALUES (:id, :match_id, 40, 'Yellow Card', :team_id, :player_id)"
            ),
            {"id": _YELLOW, "match_id": _MATCH, "team_id": _TEAM_A, "player_id": _FORWARD},
        )
        await session.commit()
        yield session
    async with SessionFactory() as cleanup:
        await cleanup.execute(text("DELETE FROM match_event WHERE match_id = :id"), {"id": _MATCH})
        await cleanup.execute(text("DELETE FROM match_lineup WHERE match_id = :id"), {"id": _MATCH})
        await cleanup.execute(
            text("DELETE FROM player_stat WHERE player_id IN (:a, :b, :c)"),
            {"a": _FORWARD, "b": _KEEPER, "c": _OPPONENT_FORWARD},
        )
        await cleanup.execute(
            text("DELETE FROM match_team_stat WHERE match_id = :id"), {"id": _MATCH}
        )
        await cleanup.execute(text("DELETE FROM match WHERE match_id = :id"), {"id": _MATCH})
        await cleanup.execute(
            text("DELETE FROM player WHERE player_id IN (:a, :b, :c)"),
            {"a": _FORWARD, "b": _KEEPER, "c": _OPPONENT_FORWARD},
        )
        await cleanup.execute(text("DELETE FROM referee WHERE referee_id = :id"), {"id": _REFEREE})
        await cleanup.execute(text("DELETE FROM venue WHERE venue_id = :id"), {"id": _VENUE})
        await cleanup.execute(
            text("DELETE FROM tournament_stage WHERE stage_id = :id"), {"id": _STAGE}
        )
        await cleanup.execute(
            text("DELETE FROM national_team WHERE team_id IN (:a, :b)"),
            {"a": _TEAM_A, "b": _TEAM_B},
        )
        await cleanup.commit()
    await engine.dispose()


async def test_get_team_comparison_aggregates_both_squads(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyTeamAnalyticsRepository(db_session)
    comparison = await repository.get_team_comparison("North Test", "STE")

    assert comparison.id == f"{_TEAM_A}-vs-{_TEAM_B}"
    assert comparison.team_a.code == "NTE"
    assert comparison.team_a.manager_name == "North Coach"
    assert comparison.team_a.fifa_ranking_pre_tournament == 4
    assert comparison.team_a.elo_rating == 1850
    assert comparison.team_a.record.won == 1
    assert comparison.team_a.record.goals_for == 2
    assert comparison.team_a.rates.xg_for == 1.8
    assert comparison.team_a.rates.possession_pct == 62
    assert comparison.team_a.discipline.yellow_cards == 1
    assert comparison.team_a.group.points == 3
    assert comparison.team_a.group.goal_difference == 1
    assert comparison.team_b.group.points == 0
    assert comparison.team_a.squad.roster_size == 2
    assert comparison.team_a.squad.total_market_value_eur == 100_000_000
    assert comparison.team_a.squad.average_age == 27.0
    assert comparison.team_a.squad.distinct_starters == 2
    assert comparison.team_a.squad.starter_minutes_share_pct == 100.0
    assert comparison.team_a.top_scorer is not None
    assert comparison.team_a.top_scorer.name == "North Forward"
    assert comparison.meetings[0].team_a_score == 2
    assert comparison.meetings[0].team_b_score == 1
    assert comparison.meetings[0].team_a_result == "W"

    groups = {group.position: group for group in comparison.positions}
    assert [player.name for player in groups["FWD"].team_a_players] == ["North Forward"]
    assert groups["FWD"].team_b_players[0].name == "South Forward"
    assert groups["GK"].team_a_players[0].saves == 3
    assert groups["GK"].team_a_players[0].goals_conceded == 1
    assert groups["DEF"].team_a_players == []
    assert comparison.team_a.squad.transfermarkt_market_value_eur is None


async def test_get_team_comparison_raises_when_a_side_is_missing(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyTeamAnalyticsRepository(db_session)
    with pytest.raises(TeamNotFoundError, match="Nowhere"):
        await repository.get_team_comparison("North Test", "Nowhere")


async def test_get_team_comparison_rejects_one_team_against_itself(
    db_session: AsyncSession,
) -> None:
    repository = _SqlAlchemyTeamAnalyticsRepository(db_session)
    with pytest.raises(SameTeamComparisonError, match="North Test"):
        await repository.get_team_comparison("North Test", "NTE")
