"""No-data cases for `query_player_stats`.

A filter matching nobody, an unknown competition, and the args-model rejections are already
pinned in `test_query_player_stats.py`; this module adds the empty-result shapes of both
datasets: teams without stat rows, minutes-based sorts over players with no minutes, and club
windows without approved links or season rows (see `no_data_cases` for the whole map).
"""

import pytest
from pydantic import ValidationError

from src.domain.chat.tools.registry import ToolDefinition
from tests.golden.no_data_cases import NO_PLAYERS_MATCHED_ERROR
from tests.golden.tools import ToolOutcome, call_tool

_TOOL = "query_player_stats"
_NO_PLAYERS = {"error": NO_PLAYERS_MATCHED_ERROR}


def _nationality(team: str) -> dict:
    return {"field": "nationality", "op": "eq", "value": team}


async def _world_cup(
    registry: dict[str, ToolDefinition], team: str, sort_by: str, *filters: dict
) -> ToolOutcome:
    return await call_tool(
        registry,
        _TOOL,
        dataset="world_cup",
        sort_by=sort_by,
        filters=[_nationality(team), *filters],
    )


async def _club(
    registry: dict[str, ToolDefinition],
    team: str,
    seasons: list[str],
    competition: str,
    *filters: dict,
) -> ToolOutcome:
    return await call_tool(
        registry,
        _TOOL,
        dataset="club_seasons",
        sort_by="goals",
        filters=[_nationality(team), *filters],
        seasons=seasons,
        competition=competition,
    )


async def test_players_with_zero_minutes_still_rank_by_a_total_stat(
    registry: dict[str, ToolDefinition],
) -> None:
    outcome = await _world_cup(registry, "Ostravia", "goals")

    rows = outcome.payload["rows"]
    assert [row["name"] for row in rows] == ["Zeno Quillfeather", "Orin Tavish"]
    assert [row["value"] for row in rows] == ["0", "0"]
    assert [row["minutes"] for row in rows] == [0, 0]
    assert outcome.widget_data is not None


@pytest.mark.parametrize(
    "sort_by", ["goals_per90", "assists_per90", "goal_contributions_per90", "saves_per90"]
)
async def test_per_90_sort_over_players_with_no_minutes_is_empty(
    registry: dict[str, ToolDefinition], sort_by: str
) -> None:
    outcome = await _world_cup(registry, "OST", sort_by)

    assert outcome.payload == _NO_PLAYERS
    assert outcome.widget_data is None


@pytest.mark.parametrize("sort_by", ["saves", "clean_sheets", "goals_conceded"])
async def test_goalkeeper_total_sort_skips_a_keeper_whose_saves_were_never_measured(
    registry: dict[str, ToolDefinition], sort_by: str
) -> None:
    outcome = await _world_cup(registry, "OST", sort_by)

    assert outcome.payload == _NO_PLAYERS
    assert outcome.widget_data is None


@pytest.mark.parametrize(
    ("team", "filters"),
    [
        ("Thalmoor", []),
        ("Atlantis", []),
        ("KRS", [{"field": "position", "op": "eq", "value": "DEF"}]),
        ("VLD", [{"field": "height_cm", "op": "gte", "value": 300}]),
        ("VLD", [{"field": "age", "op": "lte", "value": 10}]),
    ],
    ids=["team-without-roster", "unknown-team", "position-absent", "too-tall", "too-young"],
)
async def test_world_cup_filters_that_match_no_roster_row_return_the_empty_result_error(
    registry: dict[str, ToolDefinition], team: str, filters: list[dict]
) -> None:
    outcome = await _world_cup(registry, team, "goals", *filters)

    assert outcome.payload == _NO_PLAYERS
    assert outcome.widget_data is None


async def test_roster_players_without_a_stat_row_are_absent_from_the_ranking(
    registry: dict[str, ToolDefinition],
) -> None:
    """Sérvenia has three roster rows but only Lindqvist has a `player_stat` row."""
    outcome = await _world_cup(registry, "SRV", "goals")

    assert [row["name"] for row in outcome.payload["rows"]] == ["Ivo Lindqvist"]


@pytest.mark.parametrize(
    ("team", "seasons", "competition", "filters"),
    [
        ("Ostravia", ["2025"], "all", []),
        ("Karsovia", ["2025"], "all", []),
        ("Valdoria", ["2019"], "all", []),
        ("Valdoria", ["2024"], "Champions League", []),
        ("Valdoria", ["2025"], "all", [{"field": "position", "op": "eq", "value": "GK"}]),
        ("Valdoria", ["2025"], "all", [{"field": "goals", "op": "gte", "value": 99}]),
    ],
    ids=[
        "approved-link-without-season-rows",
        "no-approved-links",
        "season-window-without-rows",
        "competition-without-rows-in-window",
        "unlinked-goalkeeper",
        "filter-matches-nobody",
    ],
)
async def test_club_seasons_window_without_matching_linked_rows_returns_the_empty_result_error(
    registry: dict[str, ToolDefinition],
    team: str,
    seasons: list[str],
    competition: str,
    filters: list[dict],
) -> None:
    outcome = await _club(registry, team, seasons, competition, *filters)

    assert outcome.payload == _NO_PLAYERS
    assert outcome.widget_data is None


async def test_unrecognised_season_label_is_rejected_by_the_args_model(
    registry: dict[str, ToolDefinition],
) -> None:
    with pytest.raises(ValidationError, match="Each season must look like"):
        await _club(registry, "Valdoria", ["latest"], "all")
