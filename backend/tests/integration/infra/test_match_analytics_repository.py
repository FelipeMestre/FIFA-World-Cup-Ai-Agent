"""Integration tests against a real Postgres instance (no mocking, per
AGENTS.md's testing anti-pattern table): verifies
`_SqlAlchemyMatchAnalyticsRepository.get_match_analysis`'s aggregation across
`national_team`, `match`, `match_team_stat`, `match_event`, `match_lineup`,
`player`, and `tournament_stage` -- plus its 0-match and 2+-match (ambiguous)
branches.
"""

from collections.abc import AsyncGenerator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.match_analytics.model.match_analysis import MatchAnalysisAmbiguous
from src.infra.postgres.config import SessionFactory, engine
from src.infra.postgres.repositories.match_analytics_repository import (
    _SqlAlchemyMatchAnalyticsRepository,
)

_HOME_ID = 990501
_AWAY_ID = 990502
_STAGE_GROUP_ID = 990501
_STAGE_FINAL_ID = 990502
_VENUE_ID = 990501
_REFEREE_ID = 990501
_H_GK_ID = 990501
_H_DEF_ID = 990502
_H_MID_ID = 990503
_H_FWD_ID = 990504
_H_SUB_ID = 990505
_A_GK_ID = 990506
_A_DEF_ID = 990507
_MATCH_ID = 990501
_MATCH_ID_2 = 990502


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    async with SessionFactory() as session:
        await session.execute(
            text(
                "INSERT INTO national_team (team_id, team_name, fifa_code, confederation) "
                "VALUES (:id, 'Test Home', 'THO', 'UEFA')"
            ),
            {"id": _HOME_ID},
        )
        await session.execute(
            text(
                "INSERT INTO national_team (team_id, team_name, fifa_code, confederation) "
                "VALUES (:id, 'Test Away', 'TAW', 'CONMEBOL')"
            ),
            {"id": _AWAY_ID},
        )
        await session.execute(
            text(
                "INSERT INTO tournament_stage (stage_id, stage_name, is_knockout) "
                "VALUES (:id, 'Group Stage', false)"
            ),
            {"id": _STAGE_GROUP_ID},
        )
        await session.execute(
            text(
                "INSERT INTO tournament_stage (stage_id, stage_name, is_knockout) "
                "VALUES (:id, 'Final', true)"
            ),
            {"id": _STAGE_FINAL_ID},
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
        for player_id, team_id, name, position in (
            (_H_GK_ID, _HOME_ID, "Home Keeper", "GK"),
            (_H_DEF_ID, _HOME_ID, "Home Defender", "DF"),
            (_H_MID_ID, _HOME_ID, "Home Midfielder", "MF"),
            (_H_FWD_ID, _HOME_ID, "Home Forward", "FW"),
            (_H_SUB_ID, _HOME_ID, "Home Sub", "MF"),
            (_A_GK_ID, _AWAY_ID, "Away Keeper", "GK"),
            (_A_DEF_ID, _AWAY_ID, "Away Defender", "DF"),
        ):
            await session.execute(
                text(
                    "INSERT INTO player (player_id, team_id, player_name, position, club_team, "
                    "market_value_eur, caps, date_of_birth, height_cm, goals) "
                    "VALUES (:id, :team_id, :name, :position, 'Test Club', 1000000, 10, "
                    "'2000-01-01', 180, 5)"
                ),
                {"id": player_id, "team_id": team_id, "name": name, "position": position},
            )
        await session.execute(
            text(
                "INSERT INTO match (match_id, date, kickoff_time_utc, stage_id, venue_id, "
                "home_team_id, away_team_id, home_score, away_score, status, result_type, "
                "home_xg, away_xg, referee_id, player_of_the_match_id) "
                "VALUES (:id, '2026-06-20', '15:00:00', :stage_id, :venue_id, "
                ":home_id, :away_id, 1, 0, 'completed', 'regulation', "
                "1.2, 0.6, :referee_id, :potm_id)"
            ),
            {
                "id": _MATCH_ID,
                "stage_id": _STAGE_GROUP_ID,
                "venue_id": _VENUE_ID,
                "home_id": _HOME_ID,
                "away_id": _AWAY_ID,
                "referee_id": _REFEREE_ID,
                "potm_id": _H_FWD_ID,
            },
        )
        await session.execute(
            text(
                "INSERT INTO match (match_id, date, kickoff_time_utc, stage_id, venue_id, "
                "home_team_id, away_team_id, home_score, away_score, status, result_type, "
                "home_xg, away_xg, referee_id, player_of_the_match_id) "
                "VALUES (:id, '2026-07-10', '19:00:00', :stage_id, :venue_id, "
                ":home_id, :away_id, 2, 2, 'completed', 'regulation', "
                "1.9, 1.7, :referee_id, :potm_id)"
            ),
            {
                "id": _MATCH_ID_2,
                "stage_id": _STAGE_FINAL_ID,
                "venue_id": _VENUE_ID,
                "home_id": _HOME_ID,
                "away_id": _AWAY_ID,
                "referee_id": _REFEREE_ID,
                "potm_id": _H_FWD_ID,
            },
        )
        for team_id, possession, shots, on_target, corners, fouls, offsides in (
            (_HOME_ID, 55, 12, 5, 6, 8, 2),
            (_AWAY_ID, 45, 9, 3, 4, 10, 1),
        ):
            await session.execute(
                text(
                    "INSERT INTO match_team_stat (match_id, team_id, possession_pct, "
                    "total_shots, shots_on_target, corners, fouls, offsides, saves, "
                    "data_source, last_updated) "
                    "VALUES (:match_id, :team_id, :possession, :shots, :on_target, "
                    ":corners, :fouls, :offsides, 3, 'test', now())"
                ),
                {
                    "match_id": _MATCH_ID,
                    "team_id": team_id,
                    "possession": possession,
                    "shots": shots,
                    "on_target": on_target,
                    "corners": corners,
                    "fouls": fouls,
                    "offsides": offsides,
                },
            )
        await session.execute(
            text(
                "INSERT INTO match_event (event_id, match_id, minute, event_type, team_id, "
                "player_id) VALUES (:id, :match_id, 51, 'Goal', :team_id, :player_id)"
            ),
            {"id": 990501, "match_id": _MATCH_ID, "team_id": _HOME_ID, "player_id": _H_FWD_ID},
        )
        await session.execute(
            text(
                "INSERT INTO match_event (event_id, match_id, minute, event_type, team_id, "
                "player_id) VALUES (:id, :match_id, 51, 'Assist', :team_id, :player_id)"
            ),
            {"id": 990502, "match_id": _MATCH_ID, "team_id": _HOME_ID, "player_id": _H_MID_ID},
        )
        await session.execute(
            text(
                "INSERT INTO match_event (event_id, match_id, minute, event_type, team_id, "
                "player_id) VALUES (:id, :match_id, 70, 'Yellow Card', :team_id, :player_id)"
            ),
            {"id": 990503, "match_id": _MATCH_ID, "team_id": _AWAY_ID, "player_id": _A_DEF_ID},
        )
        for lineup_id, player_id, team_id, is_starting, tactical_position, minutes in (
            (990501, _H_GK_ID, _HOME_ID, True, "GK", 90),
            (990502, _H_DEF_ID, _HOME_ID, True, "DF", 64),
            (990503, _H_MID_ID, _HOME_ID, True, "MF", 90),
            (990504, _H_FWD_ID, _HOME_ID, True, "FW", 90),
            (990505, _H_SUB_ID, _HOME_ID, False, "MF", 26),
            (990506, _A_GK_ID, _AWAY_ID, True, "GK", 90),
            (990507, _A_DEF_ID, _AWAY_ID, True, "DF", 90),
        ):
            await session.execute(
                text(
                    "INSERT INTO match_lineup (lineup_id, match_id, player_id, team_id, "
                    "is_starting_xi, tactical_position, minutes_played) "
                    "VALUES (:lineup_id, :match_id, :player_id, :team_id, :is_starting, "
                    ":tactical_position, :minutes)"
                ),
                {
                    "lineup_id": lineup_id,
                    "match_id": _MATCH_ID,
                    "player_id": player_id,
                    "team_id": team_id,
                    "is_starting": is_starting,
                    "tactical_position": tactical_position,
                    "minutes": minutes,
                },
            )
        await session.commit()
        yield session
    async with SessionFactory() as cleanup_session:
        await cleanup_session.execute(
            text("DELETE FROM match_lineup WHERE match_id = :id"), {"id": _MATCH_ID}
        )
        await cleanup_session.execute(
            text("DELETE FROM match_event WHERE match_id = :id"), {"id": _MATCH_ID}
        )
        await cleanup_session.execute(
            text("DELETE FROM match_team_stat WHERE match_id = :id"), {"id": _MATCH_ID}
        )
        await cleanup_session.execute(
            text("DELETE FROM match WHERE match_id IN (:id, :id2)"),
            {"id": _MATCH_ID, "id2": _MATCH_ID_2},
        )
        await cleanup_session.execute(
            text(
                "DELETE FROM player WHERE player_id IN "
                "(:h_gk, :h_def, :h_mid, :h_fwd, :h_sub, :a_gk, :a_def)"
            ),
            {
                "h_gk": _H_GK_ID,
                "h_def": _H_DEF_ID,
                "h_mid": _H_MID_ID,
                "h_fwd": _H_FWD_ID,
                "h_sub": _H_SUB_ID,
                "a_gk": _A_GK_ID,
                "a_def": _A_DEF_ID,
            },
        )
        await cleanup_session.execute(
            text("DELETE FROM referee WHERE referee_id = :id"), {"id": _REFEREE_ID}
        )
        await cleanup_session.execute(
            text("DELETE FROM venue WHERE venue_id = :id"), {"id": _VENUE_ID}
        )
        await cleanup_session.execute(
            text("DELETE FROM tournament_stage WHERE stage_id IN (:id, :id2)"),
            {"id": _STAGE_GROUP_ID, "id2": _STAGE_FINAL_ID},
        )
        await cleanup_session.execute(
            text("DELETE FROM national_team WHERE team_id IN (:id, :opponent_id)"),
            {"id": _HOME_ID, "opponent_id": _AWAY_ID},
        )
        await cleanup_session.commit()
    await engine.dispose()


async def test_get_match_analysis_returns_none_when_no_match_exists(
    db_session: AsyncSession,
) -> None:
    repository = _SqlAlchemyMatchAnalyticsRepository(db_session)
    result = await repository.get_match_analysis("Test Home", "No Such Country")
    assert result is None


async def test_get_match_analysis_returns_ambiguous_for_two_matches(
    db_session: AsyncSession,
) -> None:
    repository = _SqlAlchemyMatchAnalyticsRepository(db_session)
    result = await repository.get_match_analysis("Test Home", "Test Away")
    assert isinstance(result, MatchAnalysisAmbiguous)
    assert len(result.candidates) == 2
    stage_labels = {c.stage_label for c in result.candidates}
    assert stage_labels == {"Group Stage", "Final"}


async def test_get_match_analysis_disambiguates_by_stage(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyMatchAnalyticsRepository(db_session)
    result = await repository.get_match_analysis("Test Home", "Test Away", stage="Group Stage")
    assert result is not None
    assert not isinstance(result, MatchAnalysisAmbiguous)
    assert result.id == str(_MATCH_ID)


async def test_get_match_analysis_builds_scoreboard_and_scorers(
    db_session: AsyncSession,
) -> None:
    repository = _SqlAlchemyMatchAnalyticsRepository(db_session)
    result = await repository.get_match_analysis("Test Home", "Test Away", stage="Group Stage")
    assert result is not None
    assert not isinstance(result, MatchAnalysisAmbiguous)

    assert result.home_team.code == "THO"
    assert result.away_team.code == "TAW"
    assert result.home_score == 1
    assert result.away_score == 0
    assert result.stage_label == "Group Stage"
    assert "Home Forward" in result.home_scorers
    assert "51" in result.home_scorers
    assert result.away_scorers == ""


async def test_get_match_analysis_builds_stats_split(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyMatchAnalyticsRepository(db_session)
    result = await repository.get_match_analysis("Test Home", "Test Away", stage="Group Stage")
    assert result is not None
    assert not isinstance(result, MatchAnalysisAmbiguous)

    possession_row = next(row for row in result.stats if row.label == "Possession")
    assert possession_row.home_value == "55%"
    assert possession_row.away_value == "45%"
    assert possession_row.home_pct == 55


async def test_get_match_analysis_builds_timeline_and_events(
    db_session: AsyncSession,
) -> None:
    repository = _SqlAlchemyMatchAnalyticsRepository(db_session)
    result = await repository.get_match_analysis("Test Home", "Test Away", stage="Group Stage")
    assert result is not None
    assert not isinstance(result, MatchAnalysisAmbiguous)

    assert any(event.kind == "goal" for event in result.events)
    goal_timeline_events = [e for e in result.timeline if e.kind == "goal"]
    assert len(goal_timeline_events) == 1
    assert goal_timeline_events[0].detail is not None
    assert "Home Midfielder" in goal_timeline_events[0].detail

    card_timeline_events = [e for e in result.timeline if e.kind == "card"]
    assert len(card_timeline_events) == 1
    assert card_timeline_events[0].team_code == "TAW"


async def test_get_match_analysis_builds_player_of_match(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyMatchAnalyticsRepository(db_session)
    result = await repository.get_match_analysis("Test Home", "Test Away", stage="Group Stage")
    assert result is not None
    assert not isinstance(result, MatchAnalysisAmbiguous)

    assert result.player_of_match.name == "Home Forward"
    assert result.player_of_match.team_code == "THO"
    assert result.player_of_match.position == "FWD"
    assert "1 goal" in result.player_of_match.note


async def test_get_match_analysis_builds_lineups_grouped_by_position(
    db_session: AsyncSession,
) -> None:
    repository = _SqlAlchemyMatchAnalyticsRepository(db_session)
    result = await repository.get_match_analysis("Test Home", "Test Away", stage="Group Stage")
    assert result is not None
    assert not isinstance(result, MatchAnalysisAmbiguous)

    home_lineup = next(lineup for lineup in result.lineups if lineup.code == "THO")
    group_names = {group.name for group in home_lineup.groups}
    assert "GK" in group_names
    assert "Subs used" in group_names

    subs_group = next(group for group in home_lineup.groups if group.name == "Subs used")
    assert any(player.name == "Home Sub" for player in subs_group.players)

    def_group = next(group for group in home_lineup.groups if group.name == "DEF")
    subbed_off = next(player for player in def_group.players if player.name == "Home Defender")
    assert subbed_off.mark is not None
    assert "64" in subbed_off.mark
