"""Integration tests against a real Postgres instance (no mocking, per
AGENTS.md's testing anti-pattern table): verifies
`_SqlAlchemyPlayerAnalyticsRepository.get_player_analysis` and
`.get_player_comparison`'s aggregation across `player`, `player_stat`, and
`national_team`.
"""

from collections.abc import AsyncGenerator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.chat.exceptions import chat_exceptions
from src.infra.postgres.config import SessionFactory, engine
from src.infra.postgres.repositories.player_analytics_repository import (
    _SqlAlchemyPlayerAnalyticsRepository,
)

_TEAM_ID = 990601
_PLAYER_ID = 990601
_PEER_ID = 990602
_GK_ID = 990603
_ACCENTED_PLAYER_ID = 990604


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
                "INSERT INTO player (player_id, team_id, player_name, position, club_team, "
                "market_value_eur, caps, date_of_birth, height_cm, goals) "
                "VALUES (:id, :team_id, 'Test Striker', 'FW', 'Test Club', 1000000, 10, "
                "'2000-01-01', 180, 5)"
            ),
            {"id": _PLAYER_ID, "team_id": _TEAM_ID},
        )
        await session.execute(
            text(
                "INSERT INTO player (player_id, team_id, player_name, position, club_team, "
                "market_value_eur, caps, date_of_birth, height_cm, goals) "
                "VALUES (:id, :team_id, 'Test Peer Forward', 'FW', 'Test Club', 500000, 5, "
                "'2001-01-01', 178, 1)"
            ),
            {"id": _PEER_ID, "team_id": _TEAM_ID},
        )
        await session.execute(
            text(
                "INSERT INTO player (player_id, team_id, player_name, position, club_team, "
                "market_value_eur, caps, date_of_birth, height_cm, goals) "
                "VALUES (:id, :team_id, 'Test Keeper', 'GK', 'Test Club', 300000, 3, "
                "'1998-01-01', 190, 0)"
            ),
            {"id": _GK_ID, "team_id": _TEAM_ID},
        )
        await session.execute(
            text(
                "INSERT INTO player (player_id, team_id, player_name, position, club_team, "
                "market_value_eur, caps, date_of_birth, height_cm, goals) "
                "VALUES (:id, :team_id, 'Kylian Mbappe', 'FW', 'Test Club', 2000000, 20, "
                "'1998-12-20', 178, 30)"
            ),
            {"id": _ACCENTED_PLAYER_ID, "team_id": _TEAM_ID},
        )
        await session.execute(
            text(
                "INSERT INTO player_stat (player_id, player_name, team_id, position, "
                "matches_played, matches_started, minutes_played, goals, assists, shots, "
                "shots_on_target, yellow_cards, red_cards, penalty_goals, own_goals, "
                "clean_sheets, saves, goals_conceded, average_rating, last_verified) "
                "VALUES (:id, 'Test Striker', :team_id, 'FW', 5, 5, 450, 6, 2, NULL, NULL, "
                "1, 0, 1, 0, NULL, NULL, NULL, NULL, now())"
            ),
            {"id": _PLAYER_ID, "team_id": _TEAM_ID},
        )
        await session.execute(
            text(
                "INSERT INTO player_stat (player_id, player_name, team_id, position, "
                "matches_played, matches_started, minutes_played, goals, assists, shots, "
                "shots_on_target, yellow_cards, red_cards, penalty_goals, own_goals, "
                "clean_sheets, saves, goals_conceded, average_rating, last_verified) "
                "VALUES (:id, 'Test Peer Forward', :team_id, 'FW', 5, 3, 270, 1, 0, NULL, "
                "NULL, 0, 0, 0, 0, NULL, NULL, NULL, NULL, now())"
            ),
            {"id": _PEER_ID, "team_id": _TEAM_ID},
        )
        await session.execute(
            text(
                "INSERT INTO player_stat (player_id, player_name, team_id, position, "
                "matches_played, matches_started, minutes_played, goals, assists, shots, "
                "shots_on_target, yellow_cards, red_cards, penalty_goals, own_goals, "
                "clean_sheets, saves, goals_conceded, average_rating, last_verified) "
                "VALUES (:id, 'Test Keeper', :team_id, 'GK', 5, 5, 450, 0, 0, NULL, NULL, "
                "0, 0, 0, 0, 3, 12, 4, NULL, now())"
            ),
            {"id": _GK_ID, "team_id": _TEAM_ID},
        )
        await session.execute(
            text(
                "INSERT INTO player_stat (player_id, player_name, team_id, position, "
                "matches_played, matches_started, minutes_played, goals, assists, shots, "
                "shots_on_target, yellow_cards, red_cards, penalty_goals, own_goals, "
                "clean_sheets, saves, goals_conceded, average_rating, last_verified) "
                "VALUES (:id, 'Kylian Mbappe', :team_id, 'FW', 5, 5, 450, 8, 3, NULL, NULL, "
                "0, 0, 2, 0, NULL, NULL, NULL, NULL, now())"
            ),
            {"id": _ACCENTED_PLAYER_ID, "team_id": _TEAM_ID},
        )
        await session.commit()
        yield session
    async with SessionFactory() as cleanup_session:
        await cleanup_session.execute(
            text("DELETE FROM player_stat WHERE player_id IN (:a, :b, :c, :d)"),
            {"a": _PLAYER_ID, "b": _PEER_ID, "c": _GK_ID, "d": _ACCENTED_PLAYER_ID},
        )
        await cleanup_session.execute(
            text("DELETE FROM player WHERE player_id IN (:a, :b, :c, :d)"),
            {"a": _PLAYER_ID, "b": _PEER_ID, "c": _GK_ID, "d": _ACCENTED_PLAYER_ID},
        )
        await cleanup_session.execute(
            text("DELETE FROM national_team WHERE team_id = :id"), {"id": _TEAM_ID}
        )
        await cleanup_session.commit()
    await engine.dispose()


async def test_get_player_analysis_returns_none_for_unmatched_player(
    db_session: AsyncSession,
) -> None:
    repository = _SqlAlchemyPlayerAnalyticsRepository(db_session)
    analysis = await repository.get_player_analysis("No Such Player")
    assert analysis is None


async def test_get_player_analysis_resolves_by_exact_name(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyPlayerAnalyticsRepository(db_session)
    analysis = await repository.get_player_analysis("Test Striker")

    assert analysis is not None
    assert analysis.id == str(_PLAYER_ID)
    assert analysis.name == "Test Striker"
    assert analysis.team_code == "TTA"
    assert analysis.position == "FWD"
    assert analysis.initials == "TS"
    assert analysis.club_profile is None
    assert analysis.transfers == []


async def test_get_player_analysis_resolves_by_fuzzy_substring(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyPlayerAnalyticsRepository(db_session)
    analysis = await repository.get_player_analysis("Striker")
    assert analysis is not None
    assert analysis.id == str(_PLAYER_ID)


async def test_get_player_analysis_resolves_accented_query_via_unaccent(
    db_session: AsyncSession,
) -> None:
    """DB stores the unaccented 'Kylian Mbappe'; an accented query ('Mbappé')
    must still resolve via the `unaccent` Postgres extension wrapping both
    sides of the `ILIKE` comparison in `_resolve_player`.
    """
    repository = _SqlAlchemyPlayerAnalyticsRepository(db_session)
    analysis = await repository.get_player_analysis("Mbappé")

    assert analysis is not None
    assert analysis.id == str(_ACCENTED_PLAYER_ID)
    assert analysis.name == "Kylian Mbappe"


async def test_get_player_analysis_computes_totals_and_scope(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyPlayerAnalyticsRepository(db_session)
    analysis = await repository.get_player_analysis("Test Striker")

    assert analysis is not None
    assert analysis.appearances == 5
    assert analysis.minutes == 450
    assert analysis.scope_label == "WC 2026 · 5 apps"

    goals_chip = next(c for c in analysis.chips if c.label == "Goals")
    assert goals_chip.value == "6"
    assists_chip = next(c for c in analysis.chips if c.label == "Assists")
    assert assists_chip.value == "2"
    shots_chip = next(c for c in analysis.chips if c.label == "Shots")
    assert shots_chip.value == "—"  # always-null upstream, never fabricated as 0


async def test_get_player_analysis_ranks_goal_contribution_percentile(
    db_session: AsyncSession,
) -> None:
    """This shared dev DB is not test-isolated (real seeded FWD rows sit
    alongside this fixture's own), so this only asserts internal
    consistency: the striker's own goals total/per-90, and that its
    percentile agrees with an independently-computed rank over the real
    `player_stat` FWD population -- never a hardcoded global value.
    """
    repository = _SqlAlchemyPlayerAnalyticsRepository(db_session)
    analysis = await repository.get_player_analysis("Test Striker")

    assert analysis is not None

    goals_row = next(row for row in analysis.full_breakdown if row.stat == "Goals")
    assert goals_row.total == "6"
    assert goals_row.per_ninety == "1.20"

    fwd_rows = (
        await db_session.execute(
            text(
                "SELECT goals, minutes_played FROM player_stat "
                "WHERE position ILIKE 'F%' AND minutes_played > 0"
            )
        )
    ).all()
    per90_population = [row.goals * 90 / row.minutes_played for row in fwd_rows]
    striker_per90 = 6 * 90 / 450
    below = sum(1 for v in per90_population if v < striker_per90)
    equal = sum(1 for v in per90_population if v == striker_per90)
    expected_percentile = round((below + 0.5 * equal) / len(per90_population) * 100)
    assert goals_row.percentile == expected_percentile

    minutes_row = next(row for row in analysis.full_breakdown if row.stat == "Minutes")
    assert minutes_row.percentile is None


async def test_get_player_analysis_builds_goalkeeper_chips_and_breakdown(
    db_session: AsyncSession,
) -> None:
    repository = _SqlAlchemyPlayerAnalyticsRepository(db_session)
    analysis = await repository.get_player_analysis("Test Keeper")

    assert analysis is not None
    assert analysis.position == "GK"

    saves_chip = next(c for c in analysis.chips if c.label == "Saves")
    assert saves_chip.value == "12"
    conceded_chip = next(c for c in analysis.chips if c.label == "Conceded")
    assert conceded_chip.value == "4"
    clean_sheets_chip = next(c for c in analysis.chips if c.label == "Clean sheets")
    assert clean_sheets_chip.value == "3"

    saves_benchmark = next(
        row for row in analysis.per_ninety_vs_position_average if row.label == "Saves per 90"
    )
    assert saves_benchmark.value == 2.4

    gk_rows = (
        await db_session.execute(
            text(
                "SELECT saves, minutes_played FROM player_stat "
                "WHERE position ILIKE 'G%' AND minutes_played > 0"
            )
        )
    ).all()
    per90_values = [(row.saves or 0) * 90 / row.minutes_played for row in gk_rows]
    expected_average = round(sum(per90_values) / len(per90_values), 2)
    assert saves_benchmark.position_average == expected_average


async def test_get_player_analysis_flags_card_prone_discipline(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyPlayerAnalyticsRepository(db_session)
    analysis = await repository.get_player_analysis("Test Peer Forward")

    assert analysis is not None
    assert analysis.discipline_label == "Clean record"


async def test_get_player_comparison_raises_for_unmatched_player(
    db_session: AsyncSession,
) -> None:
    repository = _SqlAlchemyPlayerAnalyticsRepository(db_session)
    with pytest.raises(chat_exceptions.PlayerNotFoundError):
        await repository.get_player_comparison("Test Striker", "No Such Player")


async def test_get_player_comparison_raises_for_same_player(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyPlayerAnalyticsRepository(db_session)
    with pytest.raises(chat_exceptions.SamePlayerComparisonError):
        await repository.get_player_comparison("Test Striker", "striker")


async def test_get_player_comparison_builds_refs_and_rows(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyPlayerAnalyticsRepository(db_session)
    comparison = await repository.get_player_comparison("Test Striker", "Test Peer Forward")

    assert comparison.normalization == "per90"
    assert comparison.player_a.id == str(_PLAYER_ID)
    assert comparison.player_a.name == "Test Striker"
    assert comparison.player_b.id == str(_PEER_ID)
    assert comparison.player_b.name == "Test Peer Forward"

    goals_row = next(row for row in comparison.rows if row.label == "Goals per 90")
    # Striker: 6 goals / 450 min -> 1.20 per 90. Peer: 1 goal / 270 min -> 0.33 per 90.
    assert goals_row.player_a_per_ninety == "1.20"
    assert goals_row.player_b_per_ninety == "0.33"
    assert goals_row.player_a_total == "6"
    assert goals_row.player_b_total == "1"
    assert goals_row.player_a_is_better is True
    assert goals_row.player_b_is_better is False
    assert goals_row.player_a_total_is_better is True
    assert goals_row.player_b_total_is_better is False

    # Goalkeeper-only stats never appear when comparing two outfield players.
    assert all("Saves" not in row.label for row in comparison.rows)
    assert all("Conceded" not in row.label for row in comparison.rows)


async def test_get_player_comparison_omits_gk_only_rows_for_mixed_positions(
    db_session: AsyncSession,
) -> None:
    repository = _SqlAlchemyPlayerAnalyticsRepository(db_session)
    comparison = await repository.get_player_comparison("Test Striker", "Test Keeper")

    assert comparison.player_a.position == "FWD"
    assert comparison.player_b.position == "GK"
    # The outfield player has no recorded saves/clean sheets/conceded, so
    # those rows are dropped rather than showing a fabricated 0.
    assert all(
        row.label not in {"Saves per 90", "Conceded per 90", "Clean sheets per 90"}
        for row in comparison.rows
    )
    assert any(row.label == "Goals per 90" for row in comparison.rows)


_CLUB_ID = 990611
_REAL_PLAYER_ID = 990611
_PENDING_REAL_PLAYER_ID = 990612


async def test_get_player_analysis_attaches_approved_club_career_only(
    db_session: AsyncSession,
) -> None:
    await db_session.execute(
        text(
            "INSERT INTO real_club (club_id, club_code, name, url) "
            "VALUES (:id, 'PSG', 'Paris Saint-Germain', 'https://example.test/psg')"
        ),
        {"id": _CLUB_ID},
    )
    await db_session.execute(
        text(
            "INSERT INTO real_player (player_id, first_name, last_name, date_of_birth, "
            "country_of_citizenship, position, sub_position, foot, height_cm, "
            "current_club_id, international_caps, international_goals, market_value_eur, "
            "highest_market_value_eur, profile_url, last_synced_at) "
            "VALUES (:id, 'Test', 'Striker', '2000-01-15', 'France', 'Attack', "
            "'Centre-Forward', 'right', 182, :club_id, 40, 18, 80000000, 120000000, "
            "'https://example.test/striker', now())"
        ),
        {"id": _REAL_PLAYER_ID, "club_id": _CLUB_ID},
    )
    await db_session.execute(
        text(
            "INSERT INTO real_player (player_id, first_name, last_name, position, "
            "profile_url, last_synced_at) "
            "VALUES (:id, 'Pending', 'Peer', 'Attack', 'https://example.test/peer', now())"
        ),
        {"id": _PENDING_REAL_PLAYER_ID},
    )
    await db_session.execute(
        text(
            "INSERT INTO player_identity_link (player_id, real_player_id, match_method, "
            "match_confidence, reviewed_by_admin, status) "
            "VALUES (:player_id, :real_id, 'EXACT_NAME_DOB', 1.000, false, 'APPROVED'), "
            "(:peer_id, :pending_id, 'FUZZY_NAME', 0.870, false, 'PENDING')"
        ),
        {
            "player_id": _PLAYER_ID,
            "real_id": _REAL_PLAYER_ID,
            "peer_id": _PEER_ID,
            "pending_id": _PENDING_REAL_PLAYER_ID,
        },
    )
    await db_session.execute(
        text(
            "INSERT INTO real_transfer (real_player_id, transfer_date, transfer_season, "
            "from_club_name, to_club_name, transfer_fee_eur, market_value_at_transfer_eur) "
            "VALUES (:id, '2019-07-01', '19/20', 'Monaco', 'Paris Saint-Germain', "
            "45000000, 60000000), "
            "(:id, '2017-07-01', '17/18', 'Youth Academy', 'Monaco', 0, 5000000)"
        ),
        {"id": _REAL_PLAYER_ID},
    )
    await db_session.commit()

    try:
        repository = _SqlAlchemyPlayerAnalyticsRepository(db_session)
        analysis = await repository.get_player_analysis("Test Striker")
        pending = await repository.get_player_analysis("Test Peer Forward")
    finally:
        await db_session.execute(
            text("DELETE FROM real_transfer WHERE real_player_id = :id"),
            {"id": _REAL_PLAYER_ID},
        )
        await db_session.execute(
            text("DELETE FROM player_identity_link WHERE player_id IN (:player_id, :peer_id)"),
            {"player_id": _PLAYER_ID, "peer_id": _PEER_ID},
        )
        await db_session.execute(
            text("DELETE FROM real_player WHERE player_id IN (:id, :pending_id)"),
            {"id": _REAL_PLAYER_ID, "pending_id": _PENDING_REAL_PLAYER_ID},
        )
        await db_session.execute(
            text("DELETE FROM real_club WHERE club_id = :id"), {"id": _CLUB_ID}
        )
        await db_session.commit()

    assert analysis is not None
    assert analysis.club_profile is not None
    profile = analysis.club_profile
    assert profile.preferred_foot == "right"
    assert profile.sub_position == "Centre-Forward"
    assert profile.height_cm == 182
    assert profile.date_of_birth.isoformat() == "2000-01-15"
    assert profile.citizenship == "France"
    assert profile.current_club == "Paris Saint-Germain"
    assert profile.market_value_eur == 80_000_000
    assert profile.highest_market_value_eur == 120_000_000
    assert profile.international_caps == 40
    assert profile.international_goals == 18
    assert [move.transfer_date.isoformat() for move in analysis.transfers] == [
        "2017-07-01",
        "2019-07-01",
    ]
    assert analysis.transfers[0].fee_eur == 0
    assert analysis.transfers[0].from_club == "Youth Academy"
    assert analysis.transfers[1].to_club == "Paris Saint-Germain"
    assert analysis.transfers[1].fee_eur == 45_000_000
    assert pending is not None
    assert pending.club_profile is None
    assert pending.transfers == []


async def test_get_player_comparison_builds_insights(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyPlayerAnalyticsRepository(db_session)
    comparison = await repository.get_player_comparison("Test Striker", "Test Peer Forward")

    assert 1 <= len(comparison.insights) <= 3
    assert all(
        "Test Striker" in insight or "Test Peer Forward" in insight
        for insight in comparison.insights
    )
