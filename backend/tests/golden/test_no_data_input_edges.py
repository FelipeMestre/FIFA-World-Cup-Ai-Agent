"""Name-input edge cases shared by every tool that resolves a name (see `no_data_cases`).

A name that cannot resolve must come back as a tool `{"error": ...}` without a widget, never
as a crash. Two inputs are different: the SQL wildcards `%` and `_` and blank or padded names
are not escaped or trimmed by the resolvers, so what they resolve to depends on whatever rows
share the database. For those, only the shape is pinned (a well-formed payload, no crash);
the behavior itself is reported as a finding.
"""

from collections.abc import Callable

import pytest
from pydantic import ValidationError

from src.domain.chat.tools.registry import ToolDefinition
from tests.golden.tools import call_tool

_MAX_NAME_LENGTH = 128
_KNOWN_TEAM = "Valdoria"
_KNOWN_PLAYER = "Rafael Ortegon"

ArgsBuilder = Callable[[str], dict]

_NAME_TOOLS: dict[str, ArgsBuilder] = {
    "get_team_analysis": lambda name: {"team_name": name},
    "get_team_comparison": lambda name: {"team_a_name": name, "team_b_name": _KNOWN_TEAM},
    "get_player_analysis": lambda name: {"player_name": name},
    "get_player_comparison": lambda name: {"player_a_name": name, "player_b_name": _KNOWN_PLAYER},
    "get_match_analysis": lambda name: {"home_team_name": name, "away_team_name": _KNOWN_TEAM},
}
_RANKING_TOOL = "query_player_stats"


def _nationality_args(name: str) -> dict:
    return {
        "dataset": "world_cup",
        "sort_by": "goals",
        "filters": [{"field": "nationality", "op": "eq", "value": name}],
    }


_ALL_TOOLS: dict[str, ArgsBuilder] = {**_NAME_TOOLS, _RANKING_TOOL: _nationality_args}
_ALL_TOOL_IDS = sorted(_ALL_TOOLS)

_UNRESOLVABLE_NAMES = {
    "longest-allowed": "x" * _MAX_NAME_LENGTH,
    "single-quote": "Zqxv'Orlath",
    "sql-injection-text": 'Zqxv"; DROP TABLE player; --',
    "unicode-and-emoji": "Zqxvñandú☃",
}
_SHAPE_ONLY_NAMES = {
    "percent": "%",
    "underscore": "_",
    "blank": "   ",
    "padded-known-team": f"  {_KNOWN_TEAM}  ",
    "padded-known-player": f"  {_KNOWN_PLAYER}  ",
}


def _assert_well_formed(outcome_payload: dict, widget_data: dict | None) -> None:
    """Either an error or a recognisable result, and a widget only alongside a result."""
    is_error = "error" in outcome_payload
    is_result = "id" in outcome_payload or "candidates" in outcome_payload
    assert is_error != is_result
    if is_error:
        assert widget_data is None


@pytest.mark.parametrize("tool_name", _ALL_TOOL_IDS)
@pytest.mark.parametrize("name", list(_UNRESOLVABLE_NAMES.values()), ids=list(_UNRESOLVABLE_NAMES))
async def test_unresolvable_text_is_reported_as_an_error_without_a_widget(
    registry: dict[str, ToolDefinition], tool_name: str, name: str
) -> None:
    outcome = await call_tool(registry, tool_name, **_ALL_TOOLS[tool_name](name))

    assert "error" in outcome.payload
    assert outcome.widget_data is None


@pytest.mark.parametrize("tool_name", sorted(_NAME_TOOLS))
async def test_name_longer_than_the_limit_is_rejected_by_the_args_model(
    registry: dict[str, ToolDefinition], tool_name: str
) -> None:
    too_long = "x" * (_MAX_NAME_LENGTH + 1)

    with pytest.raises(ValidationError, match="at most 128 characters"):
        await call_tool(registry, tool_name, **_NAME_TOOLS[tool_name](too_long))


@pytest.mark.parametrize("tool_name", _ALL_TOOL_IDS)
@pytest.mark.parametrize("name", list(_SHAPE_ONLY_NAMES.values()), ids=list(_SHAPE_ONLY_NAMES))
async def test_wildcard_blank_and_padded_names_never_crash_the_tool(
    registry: dict[str, ToolDefinition], tool_name: str, name: str
) -> None:
    outcome = await call_tool(registry, tool_name, **_ALL_TOOLS[tool_name](name))

    _assert_well_formed(outcome.payload, outcome.widget_data)


@pytest.mark.parametrize("tool_name", ["get_team_analysis", "get_match_analysis"])
async def test_team_name_with_surrounding_spaces_is_not_trimmed_and_is_reported_not_found(
    registry: dict[str, ToolDefinition], tool_name: str
) -> None:
    outcome = await call_tool(registry, tool_name, **_NAME_TOOLS[tool_name](f" {_KNOWN_TEAM} "))

    assert "error" in outcome.payload
    assert outcome.widget_data is None
