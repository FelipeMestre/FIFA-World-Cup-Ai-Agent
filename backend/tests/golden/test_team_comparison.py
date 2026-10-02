"""Golden cases for `get_team_comparison`: Valdoria vs Karsovia, same-team, not-found."""

from src.domain.chat.tools.registry import ToolDefinition
from tests.golden import expected
from tests.golden.tools import call_tool

_TOOL = "get_team_comparison"


async def test_head_to_head_carries_both_teams_records_and_group_points(
    registry: dict[str, ToolDefinition],
) -> None:
    outcome = await call_tool(registry, _TOOL, team_a_name="Valdoria", team_b_name="Karsovia")

    payload = outcome.payload
    assert payload["id"] == expected.VLD_KRS_COMPARISON_ID
    team_a, team_b = payload["team_a"], payload["team_b"]
    assert (team_a["code"], team_b["code"]) == ("VLD", "KRS")
    assert team_a["record"] == expected.VALDORIA_RECORD
    assert team_b["record"] == expected.KARSOVIA_RECORD
    assert team_a["group"] == expected.VALDORIA_GROUP
    assert team_b["group"] == expected.KARSOVIA_GROUP
    assert team_a["standing_label"] == expected.VALDORIA_STANDING_LABEL
    assert (team_a["manager_name"], team_b["manager_name"]) == (
        "Aurelio Benavente",
        "Dmitri Volkonsky",
    )
    assert (team_a["fifa_ranking_pre_tournament"], team_b["fifa_ranking_pre_tournament"]) == (7, 15)
    assert outcome.widget_data is not None


async def test_squads_are_summed_from_the_world_cup_roster(
    registry: dict[str, ToolDefinition],
) -> None:
    payload = (await call_tool(registry, _TOOL, team_a_name="VLD", team_b_name="KRS")).payload

    squad_a, squad_b = payload["team_a"]["squad"], payload["team_b"]["squad"]
    assert squad_a["roster_size"] == expected.VALDORIA_ROSTER_SIZE
    assert squad_b["roster_size"] == expected.KARSOVIA_ROSTER_SIZE
    assert squad_a["total_market_value_eur"] == expected.VALDORIA_SQUAD_MARKET_VALUE
    assert squad_b["total_market_value_eur"] == expected.KARSOVIA_SQUAD_MARKET_VALUE
    assert squad_a["transfermarkt_market_value_eur"] is None


async def test_meetings_list_both_fixtures_with_the_shootout_from_team_a_side(
    registry: dict[str, ToolDefinition],
) -> None:
    payload = (
        await call_tool(registry, _TOOL, team_a_name="Valdoria", team_b_name="Karsovia")
    ).payload

    meetings = [
        (
            row["stage"],
            row["team_a_score"],
            row["team_b_score"],
            row["team_a_result"],
            row["penalty_score"],
        )
        for row in payload["meetings"]
    ]
    assert meetings == expected.VLD_KRS_MEETINGS


async def test_positions_pair_players_by_position_group(
    registry: dict[str, ToolDefinition],
) -> None:
    payload = (
        await call_tool(registry, _TOOL, team_a_name="Valdoria", team_b_name="Karsovia")
    ).payload

    groups = {group["position"]: group for group in payload["positions"]}
    assert {p["name"] for p in groups["FWD"]["team_a_players"]} == {
        "Rafael Ortegon",
        "Dario Montefusco",
    }
    assert [p["name"] for p in groups["FWD"]["team_b_players"]] == ["Mateo Ravelli"]
    assert [p["saves"] for p in groups["GK"]["team_a_players"]] == [11]
    assert [p["saves"] for p in groups["GK"]["team_b_players"]] == [15]
    assert groups["DEF"]["team_b_players"] == []


async def test_comparing_a_team_with_itself_returns_error_naming_the_resolved_team(
    registry: dict[str, ToolDefinition],
) -> None:
    outcome = await call_tool(registry, _TOOL, team_a_name="Valdoria", team_b_name="vld")

    assert outcome.payload == {
        "error": "'Valdoria' and 'vld' both resolved to Valdoria "
        "-- pick two different teams to compare."
    }
    assert outcome.widget_data is None


async def test_unknown_team_returns_error_naming_the_failed_side(
    registry: dict[str, ToolDefinition],
) -> None:
    outcome = await call_tool(registry, _TOOL, team_a_name="Valdoria", team_b_name="Nowhereland")

    assert outcome.payload == {"error": "No team found matching 'Nowhereland'."}
    assert outcome.widget_data is None
