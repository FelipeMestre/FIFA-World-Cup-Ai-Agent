"""Golden cases for `get_player_comparison`: happy path and its three error branches."""

from src.domain.chat.tools.registry import ToolDefinition
from tests.golden import expected, fixture_data
from tests.golden.tools import call_tool

_TOOL = "get_player_comparison"


async def test_forwards_are_compared_per_90_with_the_better_side_flagged(
    registry: dict[str, ToolDefinition],
) -> None:
    outcome = await call_tool(
        registry, _TOOL, player_a_name="Rafael Ortegon", player_b_name="Dario Montefusco"
    )

    payload = outcome.payload
    assert payload["normalization"] == "per90"
    assert payload["id"] == f"{fixture_data.ORTEGON_ID}-vs-{fixture_data.MONTEFUSCO_ID}"
    assert (payload["player_a"]["name"], payload["player_b"]["name"]) == (
        "Rafael Ortegon",
        "Dario Montefusco",
    )
    goals_row = next(row for row in payload["rows"] if row["label"] == "Goals per 90")
    assert goals_row["player_a_per_ninety"] == expected.ORTEGON_GOALS_PER_90
    assert goals_row["player_b_per_ninety"] == expected.MONTEFUSCO_GOALS_PER_90
    assert (goals_row["player_a_total"], goals_row["player_b_total"]) == ("4", "2")
    assert goals_row["player_a_is_better"] is True
    assert goals_row["player_b_is_better"] is False
    assert outcome.widget_data is not None


async def test_comparison_resolves_accented_and_partial_names(
    registry: dict[str, ToolDefinition],
) -> None:
    payload = (
        await call_tool(registry, _TOOL, player_a_name="Tomas Penaranda", player_b_name="Ortegon")
    ).payload

    assert payload["player_a"]["id"] == str(fixture_data.PENARANDA_ID)
    assert payload["player_b"]["id"] == str(fixture_data.ORTEGON_ID)


async def test_goalkeeper_only_rows_are_dropped_when_comparing_with_an_outfield_player(
    registry: dict[str, ToolDefinition],
) -> None:
    payload = (
        await call_tool(
            registry, _TOOL, player_a_name="Rafael Ortegon", player_b_name="Emilio Santorini"
        )
    ).payload

    assert (payload["player_a"]["position"], payload["player_b"]["position"]) == ("FWD", "GK")
    labels = {row["label"] for row in payload["rows"]}
    assert "Goals per 90" in labels
    assert labels.isdisjoint({"Saves per 90", "Conceded per 90", "Clean sheets per 90"})


async def test_same_player_twice_returns_error_naming_the_resolved_player(
    registry: dict[str, ToolDefinition],
) -> None:
    outcome = await call_tool(
        registry, _TOOL, player_a_name="Rafael Ortegon", player_b_name="ortegon"
    )

    assert outcome.payload == {
        "error": "'Rafael Ortegon' and 'ortegon' both resolved to Rafael Ortegon "
        "-- pick two different players to compare."
    }
    assert outcome.widget_data is None


async def test_unknown_player_returns_error_naming_the_failed_side(
    registry: dict[str, ToolDefinition],
) -> None:
    outcome = await call_tool(
        registry, _TOOL, player_a_name="Rafael Ortegon", player_b_name="Zzyzx Nobody"
    )

    assert outcome.payload == {"error": "No player found matching 'Zzyzx Nobody'."}
    assert outcome.widget_data is None


async def test_roster_player_without_stats_cannot_be_compared(
    registry: dict[str, ToolDefinition],
) -> None:
    outcome = await call_tool(
        registry, _TOOL, player_a_name="Rafael Ortegon", player_b_name="Nico Falkenrath"
    )

    assert outcome.payload == {"error": "No stats recorded for 'Nico Falkenrath'."}
    assert outcome.widget_data is None
