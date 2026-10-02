"""Raw-SQL seeding and cleanup for the golden fixture (contract: see `fixture_data`)."""

from typing import NamedTuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.golden import fixture_career as career
from tests.golden import fixture_data as data
from tests.golden import fixture_matches as matches

_RANGE = {
    "lo": data.FIXTURE_ID_MIN,
    "hi": data.FIXTURE_ID_MAX,
    "rlo": data.REAL_ID_MIN,
    "rhi": data.REAL_ID_MAX,
}

# Children before parents. Every statement is confined to the fixture ID ranges.
_CLEANUP_STATEMENTS = (
    "DELETE FROM player_identity_link WHERE player_id BETWEEN :lo AND :hi "
    "OR real_player_id BETWEEN :rlo AND :rhi",
    "DELETE FROM real_player_season_stat WHERE real_player_id BETWEEN :rlo AND :rhi",
    "DELETE FROM real_transfer WHERE real_player_id BETWEEN :rlo AND :rhi",
    "DELETE FROM real_player WHERE player_id BETWEEN :rlo AND :rhi",
    "DELETE FROM real_club WHERE club_id BETWEEN :lo AND :hi",
    "DELETE FROM match_event WHERE match_id BETWEEN :lo AND :hi",
    "DELETE FROM match_lineup WHERE match_id BETWEEN :lo AND :hi",
    "DELETE FROM match_team_stat WHERE match_id BETWEEN :lo AND :hi",
    'DELETE FROM "match" WHERE match_id BETWEEN :lo AND :hi',
    "DELETE FROM player_stat WHERE player_id BETWEEN :lo AND :hi",
    "DELETE FROM player WHERE player_id BETWEEN :lo AND :hi",
    "DELETE FROM referee WHERE referee_id BETWEEN :lo AND :hi",
    "DELETE FROM venue WHERE venue_id BETWEEN :lo AND :hi",
    "DELETE FROM tournament_stage WHERE stage_id BETWEEN :lo AND :hi",
    "DELETE FROM national_team WHERE team_id BETWEEN :lo AND :hi",
)

_COUNT_STATEMENTS = {
    "national_team": "SELECT count(*) FROM national_team WHERE team_id BETWEEN :lo AND :hi",
    "player": "SELECT count(*) FROM player WHERE player_id BETWEEN :lo AND :hi",
    "match": 'SELECT count(*) FROM "match" WHERE match_id BETWEEN :lo AND :hi',
    "real_player": "SELECT count(*) FROM real_player WHERE player_id BETWEEN :rlo AND :rhi",
}


class _Insert(NamedTuple):
    sql: str
    rows: tuple


def _inserts() -> tuple[_Insert, ...]:
    return (
        _Insert(
            "INSERT INTO national_team (team_id, team_name, fifa_code, confederation, "
            "group_letter, fifa_ranking_pre_tournament, elo_rating, manager_name) VALUES "
            "(:team_id, :team_name, :fifa_code, :confederation, :group_letter, "
            ":fifa_ranking_pre_tournament, :elo_rating, :manager_name)",
            data.TEAMS,
        ),
        _Insert(
            "INSERT INTO tournament_stage (stage_id, stage_name, is_knockout) VALUES "
            "(:stage_id, :stage_name, :is_knockout)",
            (
                {
                    "stage_id": data.STAGE_GROUP_ID,
                    "stage_name": "Group Stage",
                    "is_knockout": False,
                },
                {"stage_id": data.STAGE_FINAL_ID, "stage_name": "Final", "is_knockout": True},
            ),
        ),
        _Insert(
            "INSERT INTO venue (venue_id, stadium_name, city, country, capacity, latitude, "
            "longitude, elevation_meters) VALUES (:venue_id, :stadium_name, :city, 'Fixturia', "
            "40000, 0, 0, 0)",
            (
                {
                    "venue_id": data.VENUE_ID,
                    "stadium_name": data.VENUE_NAME,
                    "city": data.VENUE_CITY,
                },
            ),
        ),
        _Insert(
            "INSERT INTO referee (referee_id, name, country, avg_cards_per_game) "
            "VALUES (:referee_id, 'Golden Referee', 'Fixturia', 3.0)",
            ({"referee_id": data.REFEREE_ID},),
        ),
        _Insert(
            "INSERT INTO player (player_id, team_id, player_name, position, club_team, "
            "market_value_eur, caps, date_of_birth, height_cm, goals) VALUES (:player_id, "
            ":team_id, :player_name, :position, :club_team, :market_value_eur, :caps, "
            ":date_of_birth, :height_cm, :goals)",
            data.PLAYERS,
        ),
        _Insert(
            "INSERT INTO player_stat (player_id, player_name, team_id, position, "
            "matches_played, matches_started, minutes_played, goals, assists, yellow_cards, "
            "red_cards, penalty_goals, own_goals, clean_sheets, saves, goals_conceded, "
            "last_verified) VALUES (:player_id, :player_name, :team_id, :position, "
            ":matches_played, :matches_started, :minutes_played, :goals, :assists, "
            ":yellow_cards, :red_cards, :penalty_goals, :own_goals, :clean_sheets, :saves, "
            ":goals_conceded, :last_verified)",
            tuple({**stat._asdict(), "last_verified": data.LAST_VERIFIED} for stat in data.STATS),
        ),
        _Insert(
            'INSERT INTO "match" (match_id, date, kickoff_time_utc, stage_id, venue_id, '
            "home_team_id, away_team_id, home_score, away_score, home_penalty_score, "
            "away_penalty_score, status, result_type, home_xg, away_xg, referee_id, "
            "player_of_the_match_id) VALUES (:match_id, :match_date, :kickoff, :stage_id, "
            ":venue_id, :home_team_id, :away_team_id, :home_score, :away_score, "
            ":home_penalty_score, :away_penalty_score, 'completed', 'regulation', :home_xg, "
            ":away_xg, :referee_id, :potm_id)",
            tuple(
                {**match._asdict(), "venue_id": data.VENUE_ID, "referee_id": data.REFEREE_ID}
                for match in matches.MATCHES
            ),
        ),
        _Insert(
            "INSERT INTO match_team_stat (match_id, team_id, possession_pct, total_shots, "
            "shots_on_target, corners, fouls, offsides, saves, data_source, last_updated) "
            "VALUES (:match_id, :team_id, :possession_pct, :total_shots, :shots_on_target, "
            ":corners, :fouls, :offsides, :saves, 'golden', now())",
            matches.TEAM_STATS,
        ),
        _Insert(
            "INSERT INTO match_event (event_id, match_id, minute, event_type, team_id, "
            "player_id) VALUES (:event_id, :match_id, :minute, :event_type, :team_id, "
            ":player_id)",
            matches.EVENTS,
        ),
        _Insert(
            "INSERT INTO match_lineup (lineup_id, match_id, player_id, team_id, "
            "is_starting_xi, tactical_position, minutes_played) VALUES (:lineup_id, "
            ":match_id, :player_id, :team_id, :is_starting_xi, :tactical_position, "
            ":minutes_played)",
            matches.LINEUPS,
        ),
        _Insert(
            "INSERT INTO real_club (club_id, club_code, name, url) "
            "VALUES (:club_id, :club_code, :name, :url)",
            career.CLUBS,
        ),
        _Insert(
            "INSERT INTO real_player (player_id, first_name, last_name, date_of_birth, "
            "country_of_citizenship, position, sub_position, foot, height_cm, "
            "current_club_id, international_caps, international_goals, market_value_eur, "
            "highest_market_value_eur, profile_url, last_synced_at) VALUES (:player_id, "
            ":first_name, :last_name, :date_of_birth, :country_of_citizenship, :position, "
            ":sub_position, :foot, :height_cm, :current_club_id, :international_caps, "
            ":international_goals, :market_value_eur, :highest_market_value_eur, "
            ":profile_url, now())",
            career.REAL_PLAYERS,
        ),
        _Insert(
            "INSERT INTO real_player_season_stat (real_player_id, season, competition_id, "
            "appearances, goals, assists, yellow_cards, red_cards, minutes_played) VALUES "
            "(:real_player_id, :season, :competition_id, :appearances, :goals, :assists, "
            ":yellow_cards, :red_cards, :minutes_played)",
            career.SEASONS,
        ),
        _Insert(
            "INSERT INTO real_transfer (real_player_id, transfer_date, transfer_season, "
            "from_club_name, to_club_name, transfer_fee_eur, market_value_at_transfer_eur) "
            "VALUES (:real_player_id, :transfer_date, :transfer_season, :from_club_name, "
            ":to_club_name, :transfer_fee_eur, :market_value_at_transfer_eur)",
            career.TRANSFERS,
        ),
        _Insert(
            "INSERT INTO player_identity_link (player_id, real_player_id, match_method, "
            "match_confidence, reviewed_by_admin, status) VALUES (:player_id, "
            ":real_player_id, :match_method, :match_confidence, false, :status)",
            career.LINKS,
        ),
    )


def _as_params(row) -> dict:
    return row if isinstance(row, dict) else row._asdict()


async def delete_fixture_rows(session: AsyncSession) -> None:
    for statement in _CLEANUP_STATEMENTS:
        await session.execute(text(statement), _RANGE)


async def seed_fixture_rows(session: AsyncSession) -> None:
    """Remove leftovers from a crashed run, then insert the whole fixture."""
    await delete_fixture_rows(session)
    for insert in _inserts():
        await session.execute(text(insert.sql), [_as_params(row) for row in insert.rows])


async def count_fixture_rows(session: AsyncSession) -> dict[str, int]:
    """Read-only leftover check, used to assert teardown really cleaned up."""
    return {
        table: (await session.execute(text(statement), _RANGE)).scalar_one()
        for table, statement in _COUNT_STATEMENTS.items()
    }
