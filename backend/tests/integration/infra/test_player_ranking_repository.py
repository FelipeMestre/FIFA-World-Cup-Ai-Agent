"""Integration tests for `query_player_stats` against real Postgres."""

from collections.abc import AsyncGenerator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.player_analytics.model.player_ranking import (
    FilterOp,
    PlayerStatField,
    QueryDataset,
    QueryPlayerStatsRequest,
    SeasonWindow,
    SortDir,
    StatFilter,
)
from src.infra.postgres.config import SessionFactory
from src.infra.postgres.repositories.player_analytics_repository import (
    _SqlAlchemyPlayerAnalyticsRepository,
)

_TEAM_ID = 990701
_FWD_A = 990701
_FWD_B = 990702
_GK = 990703
_CLUB_ID = 990711
_REAL_A = 990711
_REAL_B = 990712
_PENDING_REAL = 990713


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    async with SessionFactory() as session:
        await session.execute(
            text(
                "INSERT INTO national_team (team_id, team_name, fifa_code, confederation) "
                "VALUES (:id, 'Ranking Testland', 'RTL', 'UEFA')"
            ),
            {"id": _TEAM_ID},
        )
        await session.execute(
            text(
                "INSERT INTO player (player_id, team_id, player_name, position, club_team, "
                "market_value_eur, caps, date_of_birth, height_cm, goals) VALUES "
                "(:a, :team_id, 'Rank Forward A', 'FW', 'Club', 1, 1, '2000-01-01', 180, 0), "
                "(:b, :team_id, 'Rank Forward B', 'FW', 'Club', 1, 1, '2001-01-01', 170, 0), "
                "(:g, :team_id, 'Rank Keeper', 'GK', 'Club', 1, 1, '1998-01-01', 190, 0)"
            ),
            {"a": _FWD_A, "b": _FWD_B, "g": _GK, "team_id": _TEAM_ID},
        )
        await session.execute(
            text(
                "INSERT INTO player_stat (player_id, player_name, team_id, position, "
                "matches_played, matches_started, minutes_played, goals, assists, shots, "
                "shots_on_target, yellow_cards, red_cards, penalty_goals, own_goals, "
                "clean_sheets, saves, goals_conceded, average_rating, last_verified) VALUES "
                "(:a, 'Rank Forward A', :team_id, 'FW', 5, 5, 450, 9, 1, NULL, NULL, "
                "0, 0, 0, 0, NULL, NULL, NULL, NULL, now()), "
                "(:b, 'Rank Forward B', :team_id, 'FW', 5, 5, 450, 3, 4, NULL, NULL, "
                "2, 0, 0, 0, NULL, NULL, NULL, NULL, now()), "
                "(:g, 'Rank Keeper', :team_id, 'GK', 5, 5, 450, 0, 0, NULL, NULL, "
                "0, 0, 0, 0, 4, 20, 2, NULL, now())"
            ),
            {"a": _FWD_A, "b": _FWD_B, "g": _GK, "team_id": _TEAM_ID},
        )
        await session.commit()
        yield session
    async with SessionFactory() as cleanup_session:
        await cleanup_session.execute(
            text("DELETE FROM player_stat WHERE player_id IN (:a, :b, :g)"),
            {"a": _FWD_A, "b": _FWD_B, "g": _GK},
        )
        await cleanup_session.execute(
            text("DELETE FROM player WHERE player_id IN (:a, :b, :g)"),
            {"a": _FWD_A, "b": _FWD_B, "g": _GK},
        )
        await cleanup_session.execute(
            text("DELETE FROM national_team WHERE team_id = :id"), {"id": _TEAM_ID}
        )
        await cleanup_session.commit()


def _filter(field: PlayerStatField, op: FilterOp, value: str | int) -> StatFilter:
    return StatFilter(field=field, op=op, value=value)


def _rtl(*extra: StatFilter) -> tuple[StatFilter, ...]:
    return (_filter(PlayerStatField.NATIONALITY, FilterOp.EQ, "RTL"), *extra)


def _wc_request(**overrides) -> QueryPlayerStatsRequest:
    base = {
        "dataset": QueryDataset.WORLD_CUP,
        "sort_by": PlayerStatField.GOALS,
        "sort_dir": SortDir.DESC,
        "filters": _rtl(),
        "season_window": None,
        "competition_id": None,
        "competition_label": "all competitions",
        "limit": 10,
    }
    base.update(overrides)
    return QueryPlayerStatsRequest(**base)


async def test_world_cup_ranks_goals_on_filtered_nationality(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyPlayerAnalyticsRepository(db_session)
    ranking = await repository.query_player_stats(_wc_request())

    assert [row.player_id for row in ranking.rows] == [str(_FWD_A), str(_FWD_B), str(_GK)]
    assert ranking.rows[0].value == "9"
    assert ranking.scope_label == "WC 2026 · Goals"
    assert ranking.rows[0].goals == 9
    assert ranking.rows[0].assists == 1
    assert ranking.rows[0].appearances == 5
    assert ranking.rows[0].club_team
    assert ranking.rows[0].height_cm > 0
    assert ranking.rows[0].age > 0


async def test_world_cup_position_filter_drops_goalkeeper(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyPlayerAnalyticsRepository(db_session)
    ranking = await repository.query_player_stats(
        _wc_request(filters=_rtl(_filter(PlayerStatField.POSITION, FilterOp.EQ, "FWD")))
    )

    assert [row.player_id for row in ranking.rows] == [str(_FWD_A), str(_FWD_B)]


async def test_world_cup_saves_ranks_only_the_keeper(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyPlayerAnalyticsRepository(db_session)
    ranking = await repository.query_player_stats(_wc_request(sort_by=PlayerStatField.SAVES))

    assert [row.player_id for row in ranking.rows] == [str(_GK)]
    assert ranking.rows[0].value == "20"


async def _insert_club_stats(session: AsyncSession) -> None:
    await session.execute(
        text(
            "INSERT INTO real_club (club_id, club_code, name, url) "
            "VALUES (:id, 'RKC', 'Ranking Club', 'https://example.test/rkc')"
        ),
        {"id": _CLUB_ID},
    )
    await session.execute(
        text(
            "INSERT INTO real_player (player_id, first_name, last_name, position, "
            "profile_url, last_synced_at) VALUES "
            "(:a, 'Rank', 'A', 'Attack', 'https://example.test/a', now()), "
            "(:b, 'Rank', 'B', 'Attack', 'https://example.test/b', now()), "
            "(:p, 'Pending', 'P', 'Attack', 'https://example.test/p', now())"
        ),
        {"a": _REAL_A, "b": _REAL_B, "p": _PENDING_REAL},
    )
    await session.execute(
        text(
            "INSERT INTO player_identity_link (player_id, real_player_id, match_method, "
            "match_confidence, reviewed_by_admin, status) VALUES "
            "(:fa, :ra, 'EXACT_NAME_DOB', 1.000, true, 'APPROVED'), "
            "(:fb, :rb, 'EXACT_NAME_DOB', 1.000, true, 'APPROVED'), "
            "(:gk, :rp, 'FUZZY_NAME', 0.500, false, 'PENDING')"
        ),
        {
            "fa": _FWD_A,
            "ra": _REAL_A,
            "fb": _FWD_B,
            "rb": _REAL_B,
            "gk": _GK,
            "rp": _PENDING_REAL,
        },
    )
    await session.execute(
        text(
            "INSERT INTO real_player_season_stat (real_player_id, season, competition_id, "
            "appearances, goals, assists, yellow_cards, red_cards, minutes_played) VALUES "
            "(:a, '24/25', 'GB1', 20, 12, 3, 1, 0, 1800), "
            "(:a, '24/25', 'CL', 6, 2, 1, 0, 0, 500), "
            "(:a, '23/24', 'GB1', 30, 8, 2, 2, 0, 2500), "
            "(:b, '24/25', 'GB1', 18, 4, 7, 0, 0, 1600)"
        ),
        {"a": _REAL_A, "b": _REAL_B},
    )
    await session.commit()


async def _delete_club_stats(session: AsyncSession) -> None:
    await session.execute(
        text("DELETE FROM real_player_season_stat WHERE real_player_id IN (:a, :b)"),
        {"a": _REAL_A, "b": _REAL_B},
    )
    await session.execute(
        text("DELETE FROM player_identity_link WHERE player_id IN (:a, :b, :g)"),
        {"a": _FWD_A, "b": _FWD_B, "g": _GK},
    )
    await session.execute(
        text("DELETE FROM real_player WHERE player_id IN (:a, :b, :p)"),
        {"a": _REAL_A, "b": _REAL_B, "p": _PENDING_REAL},
    )
    await session.execute(text("DELETE FROM real_club WHERE club_id = :id"), {"id": _CLUB_ID})
    await session.commit()


def _tm_request(**overrides) -> QueryPlayerStatsRequest:
    base = {
        "dataset": QueryDataset.CLUB_SEASONS,
        "sort_by": PlayerStatField.GOALS,
        "sort_dir": SortDir.DESC,
        "filters": _rtl(),
        "season_window": SeasonWindow.LATEST,
        "competition_id": None,
        "competition_label": "all competitions",
        "limit": 10,
    }
    base.update(overrides)
    return QueryPlayerStatsRequest(**base)


async def test_transfermarkt_latest_all_sums_competitions_and_drops_pending(
    db_session: AsyncSession,
) -> None:
    await _insert_club_stats(db_session)
    try:
        repository = _SqlAlchemyPlayerAnalyticsRepository(db_session)
        ranking = await repository.query_player_stats(_tm_request())
    finally:
        await _delete_club_stats(db_session)

    assert [row.player_id for row in ranking.rows] == [str(_FWD_A), str(_FWD_B)]
    # A: 12 + 2 in 24/25; B: 4. Pending keeper omitted.
    assert ranking.rows[0].value == "14"
    assert ranking.rows[0].goals == 14
    assert ranking.rows[0].club_team
    assert ranking.rows[1].value == "4"
    assert ranking.scope_label == "Club · latest season · all competitions"


async def test_transfermarkt_named_competition_and_last_three(
    db_session: AsyncSession,
) -> None:
    await _insert_club_stats(db_session)
    try:
        repository = _SqlAlchemyPlayerAnalyticsRepository(db_session)
        ranking = await repository.query_player_stats(
            _tm_request(
                season_window=SeasonWindow.LAST_THREE,
                competition_id="GB1",
                competition_label="Premier League",
            )
        )
    finally:
        await _delete_club_stats(db_session)

    assert ranking.rows[0].player_id == str(_FWD_A)
    # 12 (24/25 GB1) + 8 (23/24 GB1)
    assert ranking.rows[0].value == "20"
    assert ranking.scope_label == "Club · last 3 seasons · Premier League"


async def test_world_cup_min_goals_drops_players_below_floor(
    db_session: AsyncSession,
) -> None:
    repository = _SqlAlchemyPlayerAnalyticsRepository(db_session)
    ranking = await repository.query_player_stats(
        _wc_request(filters=_rtl(_filter(PlayerStatField.GOALS, FilterOp.GTE, 5)))
    )

    assert [row.player_id for row in ranking.rows] == [str(_FWD_A)]


async def test_transfermarkt_min_appearances_and_goals_use_window_totals(
    db_session: AsyncSession,
) -> None:
    await _insert_club_stats(db_session)
    try:
        repository = _SqlAlchemyPlayerAnalyticsRepository(db_session)
        by_apps = await repository.query_player_stats(
            _tm_request(filters=_rtl(_filter(PlayerStatField.APPEARANCES, FilterOp.GTE, 20)))
        )
        by_goals = await repository.query_player_stats(
            _tm_request(filters=_rtl(_filter(PlayerStatField.GOALS, FilterOp.GTE, 10)))
        )
        empty = await repository.query_player_stats(
            _tm_request(
                filters=_rtl(
                    _filter(PlayerStatField.GOALS, FilterOp.GTE, 10),
                    _filter(PlayerStatField.ASSISTS, FilterOp.GTE, 10),
                )
            )
        )
    finally:
        await _delete_club_stats(db_session)

    # A: 26 apps / 14 goals / 4 assists in latest; B: 18 / 4 / 7.
    assert [row.player_id for row in by_apps.rows] == [str(_FWD_A)]
    assert [row.player_id for row in by_goals.rows] == [str(_FWD_A)]
    assert empty.rows == []
