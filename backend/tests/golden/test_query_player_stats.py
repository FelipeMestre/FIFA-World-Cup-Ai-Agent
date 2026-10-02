"""Golden cases for `query_player_stats`.

Every World Cup query adds `nationality eq <fixture team>` so results come only from
fixture rows, never from the real dataset sharing the database.
"""

import pytest
from pydantic import ValidationError

from src.domain.chat.tools.registry import ToolDefinition
from tests.golden import expected
from tests.golden.tools import ToolOutcome, call_tool

_TOOL = "query_player_stats"
_VALDORIA_ONLY = {"field": "nationality", "op": "eq", "value": "VLD"}


async def _world_cup(
    registry: dict[str, ToolDefinition], sort_by: str, *filters: dict, **extra
) -> ToolOutcome:
    return await call_tool(
        registry,
        _TOOL,
        dataset="world_cup",
        sort_by=sort_by,
        filters=[_VALDORIA_ONLY, *filters],
        **extra,
    )


def _names(outcome: ToolOutcome) -> list[str]:
    return [row["name"] for row in outcome.payload["rows"]]


async def test_sorts_descending_by_goals_and_breaks_ties_by_minutes_then_player_id(
    registry: dict[str, ToolDefinition],
) -> None:
    outcome = await _world_cup(registry, "goals")

    assert _names(outcome) == expected.VALDORIA_BY_GOALS
    assert [row["rank"] for row in outcome.payload["rows"]] == [1, 2, 3, 4, 5]
    assert outcome.payload["scope"] == "world_cup"
    assert outcome.payload["scope_label"] == "WC 2026 · Goals"
    assert outcome.widget_data is not None


async def test_limit_truncates_the_ranking(registry: dict[str, ToolDefinition]) -> None:
    outcome = await _world_cup(registry, "goals", limit=2)

    assert _names(outcome) == expected.VALDORIA_BY_GOALS[:2]
    assert outcome.payload["footer_caption"] == "2 players · tournament stats"


async def test_ascending_sort_puts_the_lowest_first(registry: dict[str, ToolDefinition]) -> None:
    outcome = await _world_cup(registry, "goals", sort_dir="asc", limit=5)

    assert _names(outcome)[-1] == "Rafael Ortegon"
    assert {row["name"] for row in outcome.payload["rows"][:3]} == (
        expected.VALDORIA_ZERO_GOAL_PLAYERS
    )


async def test_per_90_sort_formats_two_decimals_and_ignores_zero_minute_rows(
    registry: dict[str, ToolDefinition],
) -> None:
    outcome = await _world_cup(registry, "goals_per90", limit=2)

    rows = outcome.payload["rows"]
    assert [(row["name"], row["value"]) for row in rows] == [
        ("Rafael Ortegon", expected.ORTEGON_GOALS_PER_90),
        ("Dario Montefusco", expected.MONTEFUSCO_GOALS_PER_90),
    ]


async def test_goal_contributions_sums_goals_and_assists(
    registry: dict[str, ToolDefinition],
) -> None:
    outcome = await _world_cup(registry, "goal_contributions", limit=2)

    assert [(row["name"], row["value"]) for row in outcome.payload["rows"]] == [
        ("Rafael Ortegon", "5"),
        ("Dario Montefusco", "3"),
    ]


@pytest.mark.parametrize(
    ("op", "value", "expected_names"),
    [
        ("eq", 4, {"Rafael Ortegon"}),
        ("gte", 2, {"Rafael Ortegon", "Dario Montefusco"}),
        ("lte", 0, expected.VALDORIA_ZERO_GOAL_PLAYERS),
    ],
)
async def test_numeric_filter_operators_eq_gte_lte(
    registry: dict[str, ToolDefinition], op: str, value: int, expected_names: set[str]
) -> None:
    outcome = await _world_cup(registry, "goals", {"field": "goals", "op": op, "value": value})

    assert set(_names(outcome)) == expected_names


async def test_position_filter_keeps_only_that_position(
    registry: dict[str, ToolDefinition],
) -> None:
    outcome = await _world_cup(registry, "goals", {"field": "position", "op": "eq", "value": "FWD"})

    assert _names(outcome) == expected.VALDORIA_FORWARDS_BY_GOALS


async def test_goalkeeper_only_field_ranks_only_goalkeepers(
    registry: dict[str, ToolDefinition],
) -> None:
    valdoria = await _world_cup(registry, "saves")
    karsovia = await call_tool(
        registry,
        _TOOL,
        dataset="world_cup",
        sort_by="saves",
        filters=[{"field": "nationality", "op": "eq", "value": "Karsovia"}],
    )

    assert [(row["name"], row["saves"]) for row in valdoria.payload["rows"]] == [
        ("Emilio Santorini", 11)
    ]
    assert [(row["name"], row["saves"]) for row in karsovia.payload["rows"]] == [
        ("Pavel Kozhukar", 15)
    ]
    assert valdoria.payload["rows"][0]["clean_sheets"] == 1
    assert valdoria.payload["rows"][0]["goals_conceded"] == 2


async def test_filters_matching_nobody_return_the_empty_result_error(
    registry: dict[str, ToolDefinition],
) -> None:
    outcome = await _world_cup(registry, "goals", {"field": "goals", "op": "gte", "value": 99})

    assert outcome.payload == {"error": "No players matched those filters."}
    assert outcome.widget_data is None


async def test_goalkeeper_field_with_non_goalkeeper_position_is_rejected_by_the_args_model(
    registry: dict[str, ToolDefinition],
) -> None:
    with pytest.raises(ValidationError, match="goalkeeper-only"):
        await _world_cup(registry, "saves", {"field": "position", "op": "eq", "value": "FWD"})


async def test_position_with_non_equality_operator_is_rejected_by_the_args_model(
    registry: dict[str, ToolDefinition],
) -> None:
    with pytest.raises(ValidationError, match="only supports op=eq"):
        await _world_cup(registry, "goals", {"field": "position", "op": "gte", "value": "FWD"})


async def test_club_only_arguments_on_world_cup_are_rejected_by_the_args_model(
    registry: dict[str, ToolDefinition],
) -> None:
    with pytest.raises(ValidationError, match="apply only to club_seasons"):
        await _world_cup(registry, "goals", seasons=["2025"], competition="all")


async def test_unknown_position_value_is_surfaced_by_the_tool_as_an_error(
    registry: dict[str, ToolDefinition],
) -> None:
    outcome = await _world_cup(registry, "goals", {"field": "position", "op": "eq", "value": "XYZ"})

    assert outcome.payload == {"error": "position must be GK, DEF, MID, or FWD."}
    assert outcome.widget_data is None


async def test_non_numeric_filter_value_is_surfaced_by_the_tool_as_an_error(
    registry: dict[str, ToolDefinition],
) -> None:
    outcome = await _world_cup(registry, "goals", {"field": "goals", "op": "gte", "value": "lots"})

    assert outcome.payload == {"error": "Expected a number, got 'lots'."}


async def _club_goals(
    registry: dict[str, ToolDefinition], seasons: list[str], competition: str
) -> ToolOutcome:
    return await call_tool(
        registry,
        _TOOL,
        dataset="club_seasons",
        sort_by="goals",
        filters=[_VALDORIA_ONLY],
        seasons=seasons,
        competition=competition,
    )


@pytest.mark.parametrize(
    ("seasons", "competition", "label"),
    [
        (["2025"], "all", "2025 all competitions"),
        (["25/26"], "all", "2025 all competitions"),
        (["2025"], "Premier League", "2025 Premier League"),
        (["24/25", "25/26"], "all", "2024 + 2025 all competitions"),
    ],
    ids=["year", "season-label", "single-competition", "two-seasons"],
)
async def test_club_seasons_sum_only_approved_linked_players(
    registry: dict[str, ToolDefinition], seasons: list[str], competition: str, label: str
) -> None:
    outcome = await _club_goals(registry, seasons, competition)

    rows = outcome.payload["rows"]
    # Montefusco's link is pending, so only Ortegon appears.
    assert [(row["name"], row["value"]) for row in rows] == [
        ("Rafael Ortegon", expected.ORTEGON_CLUB_GOALS[label])
    ]
    assert outcome.payload["scope"] == "transfermarkt"
    assert outcome.payload["footer_caption"] == "1 players · approved Transfermarkt links only"


async def test_club_seasons_with_unknown_competition_is_surfaced_as_an_error(
    registry: dict[str, ToolDefinition],
) -> None:
    outcome = await _club_goals(registry, ["2025"], "Atlantis League")

    assert outcome.payload["error"].startswith("No competition matching 'Atlantis League'.")


async def test_club_seasons_without_seasons_is_rejected_by_the_args_model(
    registry: dict[str, ToolDefinition],
) -> None:
    with pytest.raises(ValidationError, match="seasons and competition are required"):
        await call_tool(registry, _TOOL, dataset="club_seasons", sort_by="goals")


async def test_world_cup_only_field_on_club_seasons_is_rejected_by_the_args_model(
    registry: dict[str, ToolDefinition],
) -> None:
    with pytest.raises(ValidationError, match="not available on club_seasons"):
        await call_tool(
            registry,
            _TOOL,
            dataset="club_seasons",
            sort_by="saves",
            seasons=["2025"],
            competition="all",
        )
