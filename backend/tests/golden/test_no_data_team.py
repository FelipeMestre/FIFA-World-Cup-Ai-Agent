"""No-data cases for `get_team_analysis` and `get_team_comparison`.

Unknown-team and same-team errors are already pinned in `test_team_analysis.py` and
`test_team_comparison.py`; this module adds the teams that exist but have little or nothing
behind them (see `no_data_cases` for the whole map).
"""

import pytest

from src.domain.chat.tools.registry import ToolDefinition
from tests.golden import fixture_data
from tests.golden.fixture_empty import OSTRAVIA, THALMOOR
from tests.golden.no_data_cases import UNKNOWN_TEAM, UNKNOWN_TEAM_ERROR
from tests.golden.tools import call_tool

_ANALYSIS = "get_team_analysis"
_COMPARISON = "get_team_comparison"
_ZERO_RECORD = {"won": 0, "drawn": 0, "lost": 0, "goals_for": 0, "goals_against": 0}
_ZERO_GROUP = {"played": 0, "points": 0, "goal_difference": 0}
_ZERO_AVERAGES = {
    "Possession": "0.0%",
    "Shots": "0.0",
    "Shots on target": "0.0",
    "Corners": "0.0",
    "Fouls": "0.0",
    "Offsides": "0.0",
}
_OSTRAVIA_SQUAD_MARKET_VALUE = 2_500_000  # 1.0 + 1.5 million
_EMPTY_POSITION_ORDER = ["GK", "DEF", "MID", "FWD"]


async def test_team_that_never_played_reports_a_zero_record_with_placeholder_labels(
    registry: dict[str, ToolDefinition],
) -> None:
    outcome = await call_tool(registry, _ANALYSIS, team_name="Ostravia")

    payload = outcome.payload
    assert payload["id"] == str(OSTRAVIA.team_id)
    assert payload["scope_label"] == "WC 2026 · 0 matches"
    assert payload["standing_label"] == "Did not qualify"
    assert payload["stage_caption"] == "Did not play"
    assert payload["record"] == _ZERO_RECORD
    assert payload["goal_difference"] == 0
    assert payload["conceded_per_game"] == 0.0
    assert payload["clean_sheets"] == 0
    assert payload["avg_possession_pct"] == 0.0
    assert payload["group"] == _ZERO_GROUP
    # The team exists, so a widget is still produced; it just carries zeros.
    assert outcome.widget_data is not None


async def test_team_that_never_played_has_empty_match_lists_and_zero_discipline(
    registry: dict[str, ToolDefinition],
) -> None:
    payload = (await call_tool(registry, _ANALYSIS, team_name="OST")).payload

    assert payload["match_results"] == []
    assert payload["goals_by_match"] == []
    discipline = payload["discipline"]
    assert (discipline["yellow_cards"], discipline["red_cards"], discipline["fouls"]) == (0, 0, 0)
    assert discipline["yellow_per_match"] == 0.0
    averages = {row["label"]: row["value"] for row in payload["tournament_averages"]}
    for label, value in _ZERO_AVERAGES.items():
        assert averages[label] == value


async def test_team_that_never_played_has_no_squad_leaders_even_with_a_roster(
    registry: dict[str, ToolDefinition],
) -> None:
    payload = (await call_tool(registry, _ANALYSIS, team_name="Ostravia")).payload

    assert payload["top_scorer"] is None
    assert payload["top_assister"] is None
    assert payload["most_minutes"] is None
    squad = payload["squad"]
    assert squad["roster_size"] == 2
    assert squad["total_market_value_eur"] == _OSTRAVIA_SQUAD_MARKET_VALUE
    assert squad["distinct_starters"] == 0
    assert squad["starter_minutes_share_pct"] == 0.0
    assert squad["transfermarkt_average_age"] is None


async def test_roster_players_without_matches_are_listed_with_zero_or_unmeasured_stats(
    registry: dict[str, ToolDefinition],
) -> None:
    payload = (await call_tool(registry, _ANALYSIS, team_name="Ostravia")).payload

    players = {
        player["name"]: player for group in payload["positions"] for player in group["players"]
    }
    assert set(players) == {"Zeno Quillfeather", "Orin Tavish"}
    keeper = players["Zeno Quillfeather"]
    assert (keeper["appearances"], keeper["minutes"], keeper["goals"]) == (0, 0, 0)
    assert keeper["saves"] is None
    assert keeper["clean_sheets"] is None
    assert keeper["goals_conceded"] is None
    assert keeper["saves_per90"] is None
    assert players["Orin Tavish"]["goals_per90"] == 0.0


async def test_team_without_a_roster_or_matches_has_an_empty_squad(
    registry: dict[str, ToolDefinition],
) -> None:
    outcome = await call_tool(registry, _ANALYSIS, team_name="Thalmoor")

    payload = outcome.payload
    assert payload["id"] == str(THALMOOR.team_id)
    squad = payload["squad"]
    assert squad["roster_size"] == 0
    assert squad["average_age"] is None
    assert squad["youngest_age"] is None
    assert squad["oldest_age"] is None
    assert squad["total_market_value_eur"] == 0
    assert [group["position"] for group in payload["positions"]] == _EMPTY_POSITION_ORDER
    assert all(group["players"] == [] for group in payload["positions"])
    assert payload["record"] == _ZERO_RECORD
    assert outcome.widget_data is not None


async def test_team_whose_players_never_scored_has_no_top_scorer_but_a_minutes_leader(
    registry: dict[str, ToolDefinition],
) -> None:
    """Sérvenia: one 90-minute player with no goals, and two roster rows with no stat row."""
    payload = (await call_tool(registry, _ANALYSIS, team_name="Sérvenia")).payload

    assert payload["squad"]["roster_size"] == 3
    assert payload["top_scorer"] is None
    assert payload["top_assister"] is None
    assert payload["most_minutes"]["name"] == "Ivo Lindqvist"
    assert payload["most_minutes"]["minutes"] == 90


async def test_comparing_two_teams_that_never_played_has_no_meetings_or_edges(
    registry: dict[str, ToolDefinition],
) -> None:
    outcome = await call_tool(registry, _COMPARISON, team_a_name="Ostravia", team_b_name="Thalmoor")

    payload = outcome.payload
    assert payload["meetings"] == []
    assert payload["strengths_and_flaws"] == []
    assert payload["team_a"]["standing_label"] == payload["team_b"]["standing_label"]
    assert payload["team_a"]["standing_label"] == "Did not qualify"
    assert payload["team_a"]["record"] == _ZERO_RECORD
    assert payload["team_b"]["record"] == _ZERO_RECORD
    for stat in payload["compared_stats"]:
        assert (stat["team_a_value"], stat["team_b_value"]) == (0.0, 0.0)
        assert not stat["team_a_is_better"]
        assert not stat["team_b_is_better"]
    # Both teams exist, so the comparison still produces a widget.
    assert outcome.widget_data is not None


async def test_comparing_a_team_with_results_against_one_that_never_played(
    registry: dict[str, ToolDefinition],
) -> None:
    payload = (
        await call_tool(registry, _COMPARISON, team_a_name="Valdoria", team_b_name="Ostravia")
    ).payload

    assert payload["id"] == f"{fixture_data.VALDORIA.team_id}-vs-{OSTRAVIA.team_id}"
    assert payload["meetings"] == []
    assert payload["team_a"]["match_results"] != []
    assert payload["team_b"]["match_results"] == []
    assert payload["team_b"]["record"] == _ZERO_RECORD
    assert payload["team_b"]["stage_caption"] == "Did not play"
    squads = {group["position"]: group for group in payload["positions"]}
    assert squads["GK"]["team_b_players"][0]["name"] == "Zeno Quillfeather"
    assert squads["GK"]["team_b_players"][0]["saves"] is None


@pytest.mark.parametrize(
    ("team_a", "team_b"),
    [(UNKNOWN_TEAM, "Valdoria"), (UNKNOWN_TEAM, "Another Fictional Side")],
    ids=["unknown-first-side", "both-unknown"],
)
async def test_unknown_first_team_is_the_one_named_in_the_error(
    registry: dict[str, ToolDefinition], team_a: str, team_b: str
) -> None:
    outcome = await call_tool(registry, _COMPARISON, team_a_name=team_a, team_b_name=team_b)

    assert outcome.payload == {"error": UNKNOWN_TEAM_ERROR}
    assert outcome.widget_data is None
