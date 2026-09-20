"""Pure unit tests for `PlayerIdentityMatchingService` -- fixture player lists
covering the 3 confidence tiers and their exact boundaries (0.850, 0.950,
1.000), plus the below-floor discard case. No DB/HTTP.
"""

from datetime import date
from decimal import Decimal

from src.domain.ingestion.model.player_identity_link import PlayerMatchMethod
from src.domain.ingestion.services.player_identity_matching_service import (
    PlayerIdentityMatchingService,
)
from src.domain.players.model.player import Player


def _player(
    player_id: int,
    name: str,
    dob: date = date(2000, 1, 1),
    team_id: int = 1,
) -> Player:
    return Player(
        id=player_id,
        team_id=team_id,
        name=name,
        position="FW",
        club_team="Some FC",
        market_value_eur=1_000_000,
        caps=10,
        date_of_birth=dob,
        height_cm=180,
        goals=5,
    )


def _real_player(
    real_player_id: int,
    first_name: str,
    last_name: str,
    dob: date | None = date(2000, 1, 1),
    national_team_id: int | None = 1,
    height_in_cm: int | None = 180,
) -> dict:
    return {
        "player_id": real_player_id,
        "first_name": first_name,
        "last_name": last_name,
        "date_of_birth": dob,
        "current_national_team_id": national_team_id,
        "height_in_cm": height_in_cm,
    }


def test_exact_name_and_dob_matches_with_confidence_1_000() -> None:
    synthetic = [_player(1, "Lionel Messi", dob=date(1987, 6, 24), team_id=10)]
    real = [_real_player(500, "Lionel", "Messi", dob=date(1987, 6, 24), national_team_id=99)]

    candidates = PlayerIdentityMatchingService().match(
        synthetic, real, national_team_id_by_team_id={10: 99}
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.player_id == 1
    assert candidate.real_player_id == 500
    assert candidate.match_method == PlayerMatchMethod.EXACT_NAME_DOB
    assert candidate.match_confidence == Decimal("1.000")


def test_exact_name_and_team_no_dob_match_scores_0_950() -> None:
    synthetic = [_player(1, "Kylian Mbappe", dob=date(1998, 12, 20), team_id=10)]
    real = [_real_player(500, "Kylian", "Mbappe", dob=date(1999, 1, 1), national_team_id=99)]

    candidates = PlayerIdentityMatchingService().match(
        synthetic, real, national_team_id_by_team_id={10: 99}
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.match_method == PlayerMatchMethod.EXACT_NAME_TEAM
    assert candidate.match_confidence == Decimal("0.950")


def test_fuzzy_name_match_falls_in_tier_range() -> None:
    synthetic = [_player(1, "Robert Lewandowski", dob=date(1988, 8, 21), team_id=10)]
    real = [_real_player(500, "Robert", "Lewandovski", dob=date(1975, 5, 5), national_team_id=42)]

    candidates = PlayerIdentityMatchingService().match(
        synthetic, real, national_team_id_by_team_id={10: 99}
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.match_method == PlayerMatchMethod.FUZZY_NAME
    assert Decimal("0.850") <= candidate.match_confidence < Decimal("0.950")


def test_fuzzy_name_corroborated_by_dob_and_height_auto_accepts_at_0_950() -> None:
    # User-reported gap: a fuzzy name match with a confirmed DOB and height
    # should auto-accept, not sit in the review queue capped below 0.950.
    synthetic = [_player(1, "Robert Lewandowski", dob=date(1988, 8, 21), team_id=10)]
    real = [
        _real_player(
            500,
            "Robert",
            "Lewandovski",
            dob=date(1988, 8, 21),
            national_team_id=42,
            height_in_cm=180,
        )
    ]

    candidates = PlayerIdentityMatchingService().match(
        synthetic, real, national_team_id_by_team_id={10: 99}
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.match_method == PlayerMatchMethod.FUZZY_NAME
    assert candidate.match_confidence == Decimal("0.950")


def test_corroborated_candidate_preferred_over_higher_raw_score_uncorroborated() -> None:
    synthetic = [_player(1, "Robert Lewandowski", dob=date(1988, 8, 21), team_id=10)]
    real = [
        # Closer name match, but DOB/height don't confirm it.
        _real_player(
            500, "Robert", "Lewandowsk", dob=date(1975, 5, 5), national_team_id=42, height_in_cm=175
        ),
        # Slightly worse name match, but DOB and height both confirm it.
        _real_player(
            501,
            "Robert",
            "Lewandovski",
            dob=date(1988, 8, 21),
            national_team_id=42,
            height_in_cm=180,
        ),
    ]

    candidates = PlayerIdentityMatchingService().match(
        synthetic, real, national_team_id_by_team_id={10: 99}
    )

    assert len(candidates) == 1
    assert candidates[0].real_player_id == 501
    assert candidates[0].match_confidence == Decimal("0.950")


def test_below_floor_match_is_discarded() -> None:
    synthetic = [_player(1, "Someone Completely Different", dob=date(2000, 1, 1), team_id=10)]
    real = [_real_player(500, "Totally", "Unrelated", dob=date(1975, 5, 5), national_team_id=42)]

    candidates = PlayerIdentityMatchingService().match(
        synthetic, real, national_team_id_by_team_id={10: 99}
    )

    assert candidates == []
