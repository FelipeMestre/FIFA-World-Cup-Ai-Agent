"""Golden cases for `get_team_analysis`: resolution paths and the Valdoria record."""

import pytest

from src.domain.chat.tools.registry import ToolDefinition
from tests.golden import expected, fixture_data
from tests.golden.tools import call_tool

_TOOL = "get_team_analysis"


@pytest.mark.parametrize(
    "query",
    ["VLD", "vld", "Valdoria", "valdoria", "aldor"],
    ids=["code", "code-lowercase", "exact-name", "name-lowercase", "substring"],
)
async def test_team_resolves_from_code_name_and_substring(
    registry: dict[str, ToolDefinition], query: str
) -> None:
    outcome = await call_tool(registry, _TOOL, team_name=query)

    assert outcome.payload["id"] == str(fixture_data.VALDORIA.team_id)
    assert outcome.payload["code"] == "VLD"
    assert outcome.payload["name"] == "Valdoria"


@pytest.mark.parametrize("query", ["Sérvenia", "SRV"], ids=["accented-name", "code"])
async def test_accented_team_name_resolves(registry: dict[str, ToolDefinition], query: str) -> None:
    outcome = await call_tool(registry, _TOOL, team_name=query)

    assert outcome.payload["id"] == str(fixture_data.SERVENIA.team_id)
    assert outcome.payload["name"] == "Sérvenia"


@pytest.mark.parametrize("query", ["Nowhereland", "Valdoira"], ids=["unknown", "misspelled"])
async def test_unresolvable_team_returns_not_found_error_without_widget(
    registry: dict[str, ToolDefinition], query: str
) -> None:
    outcome = await call_tool(registry, _TOOL, team_name=query)

    assert outcome.payload == {"error": f"No team found matching '{query}'."}
    assert outcome.widget_data is None


async def test_valdoria_record_goals_and_standing(registry: dict[str, ToolDefinition]) -> None:
    payload = (await call_tool(registry, _TOOL, team_name="Valdoria")).payload

    assert payload["scope_label"] == expected.VALDORIA_SCOPE_LABEL
    assert payload["record"] == expected.VALDORIA_RECORD
    assert payload["goal_difference"] == expected.VALDORIA_GOAL_DIFFERENCE
    assert payload["conceded_per_game"] == expected.VALDORIA_CONCEDED_PER_GAME
    assert payload["clean_sheets"] == expected.VALDORIA_CLEAN_SHEETS
    assert payload["avg_possession_pct"] == expected.VALDORIA_AVG_POSSESSION
    assert payload["standing_label"] == expected.VALDORIA_STANDING_LABEL
    assert payload["stage_caption"] == expected.VALDORIA_STAGE_CAPTION


async def test_valdoria_match_results_are_chronological_and_score_the_shootout_loss(
    registry: dict[str, ToolDefinition],
) -> None:
    payload = (await call_tool(registry, _TOOL, team_name="Valdoria")).payload

    results = [
        (row["stage"], row["opponent_code"], row["score"], row["result"])
        for row in payload["match_results"]
    ]
    assert results == expected.VALDORIA_MATCH_RESULTS
    assert [row["opponent_name"] for row in payload["match_results"]][1] == "Sérvenia"


async def test_valdoria_discipline_and_group_points_exclude_knockout(
    registry: dict[str, ToolDefinition],
) -> None:
    payload = (await call_tool(registry, _TOOL, team_name="Valdoria")).payload

    discipline = payload["discipline"]
    for field, value in expected.VALDORIA_DISCIPLINE.items():
        assert discipline[field] == value
    assert payload["group"] == expected.VALDORIA_GROUP


async def test_valdoria_identity_and_squad_leader(registry: dict[str, ToolDefinition]) -> None:
    payload = (await call_tool(registry, _TOOL, team_name="Valdoria")).payload

    assert payload["confederation"] == "UEFA"
    assert payload["group_letter"] == "X"
    assert payload["manager_name"] == "Aurelio Benavente"
    assert payload["fifa_ranking_pre_tournament"] == 7
    assert payload["squad"]["roster_size"] == expected.VALDORIA_ROSTER_SIZE
    assert payload["top_scorer"]["name"] == expected.VALDORIA_TOP_SCORER
    assert payload["top_scorer"]["goals"] == 4


async def test_roster_is_grouped_by_position(registry: dict[str, ToolDefinition]) -> None:
    payload = (await call_tool(registry, _TOOL, team_name="Valdoria")).payload

    names_by_position = {
        group["position"]: {player["name"] for player in group["players"]}
        for group in payload["positions"]
    }
    assert names_by_position == {
        "GK": {"Emilio Santorini"},
        "DEF": {"Mateo Ravelli"},
        "MID": {"Tomás Peñaranda"},
        "FWD": {"Rafael Ortegon", "Dario Montefusco"},
    }


async def test_other_teams_get_their_own_records(registry: dict[str, ToolDefinition]) -> None:
    karsovia = (await call_tool(registry, _TOOL, team_name="KRS")).payload
    servenia = (await call_tool(registry, _TOOL, team_name="SRV")).payload

    assert karsovia["record"] == expected.KARSOVIA_RECORD
    assert karsovia["group"] == expected.KARSOVIA_GROUP
    assert servenia["record"] == expected.SERVENIA_RECORD
    assert servenia["clean_sheets"] == 0
