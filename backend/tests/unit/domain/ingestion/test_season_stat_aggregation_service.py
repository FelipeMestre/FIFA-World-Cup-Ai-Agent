"""Pure unit tests for `SeasonStatAggregationService` -- in-memory fixtures
only, no DB/HTTP. `appearances.csv` has no `season` column directly, so the
service must join each appearance row to its game (by `game_id`) to recover
`season`/`competition_id` before grouping.
"""

import pytest

from src.domain.ingestion.exceptions.ingestion_exceptions import IngestionValidationError
from src.domain.ingestion.services.season_stat_aggregation_service import (
    SeasonStatAggregationService,
)

_GAMES_BY_ID = {
    "g1": {"season": "2023", "competition_id": "L1"},
    "g2": {"season": "2023", "competition_id": "L1"},
    "g3": {"season": "2024", "competition_id": "L1"},
}


def _appearance(
    game_id: str,
    player_id: int = 100,
    yellow_cards: int = 0,
    red_cards: int = 0,
    goals: int = 0,
    assists: int = 0,
    minutes_played: int = 90,
) -> dict:
    return {
        "player_id": player_id,
        "game_id": game_id,
        "yellow_cards": yellow_cards,
        "red_cards": red_cards,
        "goals": goals,
        "assists": assists,
        "minutes_played": minutes_played,
    }


def test_aggregates_two_appearances_in_same_season_and_competition() -> None:
    rows = [
        _appearance("g1", goals=1, assists=0, minutes_played=90, yellow_cards=1),
        _appearance("g2", goals=2, assists=1, minutes_played=75, red_cards=1),
    ]

    result = SeasonStatAggregationService().aggregate(rows, _GAMES_BY_ID)

    assert len(result) == 1
    row = result[0]
    assert row["real_player_id"] == 100
    assert row["season"] == "2023"
    assert row["competition_id"] == "L1"
    assert row["appearances"] == 2
    assert row["goals"] == 3
    assert row["assists"] == 1
    assert row["yellow_cards"] == 1
    assert row["red_cards"] == 1
    assert row["minutes_played"] == 165


def test_splits_by_differing_season() -> None:
    rows = [
        _appearance("g1", goals=1),
        _appearance("g3", goals=5),
    ]

    result = SeasonStatAggregationService().aggregate(rows, _GAMES_BY_ID)

    by_season = {row["season"]: row for row in result}
    assert set(by_season) == {"2023", "2024"}
    assert by_season["2023"]["goals"] == 1
    assert by_season["2024"]["goals"] == 5


def test_splits_by_differing_player() -> None:
    rows = [
        _appearance("g1", player_id=100, goals=1),
        _appearance("g1", player_id=200, goals=9),
    ]

    result = SeasonStatAggregationService().aggregate(rows, _GAMES_BY_ID)

    by_player = {row["real_player_id"]: row for row in result}
    assert by_player[100]["goals"] == 1
    assert by_player[200]["goals"] == 9


def test_missing_game_id_raises_validation_error() -> None:
    rows = [_appearance("unknown_game")]

    with pytest.raises(IngestionValidationError):
        SeasonStatAggregationService().aggregate(rows, _GAMES_BY_ID)
