"""No-data cases for `get_player_analysis` and `get_player_comparison`.

Unknown player, roster player without stats or career, the same-name career fallback,
pending links and the retired / free-agent career labels are already pinned in
`test_player_analysis.py` and `test_player_comparison.py`; this module adds the players
whose data exists but is empty or unmeasured (see `no_data_cases` for the whole map).
"""

from src.domain.chat.tools.registry import ToolDefinition
from tests.golden.fixture_empty import QUILLFEATHER_ID, TAVISH_ID, THORNCASTLE_REAL_ID
from tests.golden.no_data_cases import UNKNOWN_PLAYER, UNKNOWN_PLAYER_ERROR
from tests.golden.tools import call_tool

_ANALYSIS = "get_player_analysis"
_COMPARISON = "get_player_comparison"
_UNMEASURED_CHIP = "—"
_GOALKEEPER_ONLY_ROWS = {"Saves per 90", "Conceded per 90", "Clean sheets per 90"}
_CAREER_BREAKDOWN_STATS = [
    "Appearances",
    "Goals",
    "Assists",
    "Yellow cards",
    "Red cards",
    "Minutes",
]


def _chips(payload: dict) -> dict[str, str]:
    return {chip["label"]: chip["value"] for chip in payload["chips"]}


def _rows(payload: dict) -> dict[str, dict]:
    return {row["stat"]: row for row in payload["full_breakdown"]}


async def test_player_with_a_stat_row_of_zero_minutes_reports_zero_totals(
    registry: dict[str, ToolDefinition],
) -> None:
    outcome = await call_tool(registry, _ANALYSIS, player_name="Orin Tavish")

    payload = outcome.payload
    assert payload["id"] == str(TAVISH_ID)
    assert payload["team_code"] == "OST"
    assert (payload["appearances"], payload["minutes"]) == (0, 0)
    assert payload["scope_label"] == "WC 2026 · 0 apps"
    assert payload["footer_caption"] == "0 apps · 0 min · verified 2026-07-20"
    chips = _chips(payload)
    assert (chips["Goals"], chips["Assists"], chips["Minutes"]) == ("0", "0", "0")
    assert chips["Shots"] == _UNMEASURED_CHIP
    rows = _rows(payload)
    assert (rows["Goals"]["total"], rows["Goals"]["per_ninety"]) == ("0", "0.00")
    assert (rows["Minutes"]["total"], rows["Minutes"]["per_ninety"]) == ("0", "0.00")
    assert rows["Minutes"]["percentile"] is None
    assert outcome.widget_data is not None


async def test_approved_link_to_a_career_without_seasons_or_transfers_gives_a_bare_profile(
    registry: dict[str, ToolDefinition],
) -> None:
    payload = (await call_tool(registry, _ANALYSIS, player_name="Orin Tavish")).payload

    profile = payload["club_profile"]
    assert profile is not None
    assert profile["is_retired"] is True
    assert profile["current_club"] is None
    assert profile["market_value_eur"] is None
    assert profile["preferred_foot"] is None
    assert profile["date_of_birth"] is None
    assert payload["transfers"] == []
    assert payload["career_seasons"] == []


async def test_goalkeeper_with_unmeasured_saves_shows_dash_chips_and_no_derived_rows(
    registry: dict[str, ToolDefinition],
) -> None:
    payload = (await call_tool(registry, _ANALYSIS, player_name="Zeno Quillfeather")).payload

    assert payload["id"] == str(QUILLFEATHER_ID)
    assert payload["position"] == "GK"
    chips = _chips(payload)
    assert chips["Saves"] == _UNMEASURED_CHIP
    assert chips["Clean sheets"] == _UNMEASURED_CHIP
    assert chips["Conceded"] == _UNMEASURED_CHIP
    assert chips["Minutes"] == "0"
    assert {"Goals conceded", "Clean sheets"}.isdisjoint(_rows(payload))


async def test_wc_player_without_any_identity_link_has_no_club_data(
    registry: dict[str, ToolDefinition],
) -> None:
    payload = (await call_tool(registry, _ANALYSIS, player_name="Ivo Lindqvist")).payload

    assert payload["club_profile"] is None
    assert payload["transfers"] == []
    assert payload["career_seasons"] == []


async def test_career_record_with_no_seasons_no_transfers_and_no_club_reports_zero_totals(
    registry: dict[str, ToolDefinition],
) -> None:
    outcome = await call_tool(registry, _ANALYSIS, player_name="Wendell Thorncastle")

    payload = outcome.payload
    assert payload["id"] == str(THORNCASTLE_REAL_ID)
    assert payload["name"] == "Wendell Thorncastle"
    assert payload["position"] == "DEF"
    assert payload["scope_label"] == "Club career · totals"
    assert payload["tier_label"] == "Club career"
    assert payload["team_code"] == "RETIRED"
    assert (payload["appearances"], payload["minutes"]) == (0, 0)
    assert payload["footer_caption"] == "0 apps · 0 min · club career totals"
    chips = _chips(payload)
    assert (chips["Goals"], chips["Assists"], chips["Appearances"], chips["Minutes"]) == (
        "0",
        "0",
        "0",
        "0",
    )
    assert [row["stat"] for row in payload["full_breakdown"]] == _CAREER_BREAKDOWN_STATS
    assert all(row["total"] == "0" for row in payload["full_breakdown"])
    assert all(row["percentile"] is None for row in payload["full_breakdown"])
    assert payload["per_ninety_vs_position_average"] == []
    assert payload["club_profile"]["is_retired"] is True
    assert payload["transfers"] == []
    assert payload["career_seasons"] == []
    assert outcome.widget_data is not None


async def test_comparison_with_a_zero_minute_player_reports_zero_rates_for_that_side(
    registry: dict[str, ToolDefinition],
) -> None:
    outcome = await call_tool(
        registry, _COMPARISON, player_a_name="Rafael Ortegon", player_b_name="Orin Tavish"
    )

    payload = outcome.payload
    assert payload["player_b"]["minutes"] == 0
    goals_row = next(row for row in payload["rows"] if row["label"] == "Goals per 90")
    assert (goals_row["player_b_per_ninety"], goals_row["player_b_total"]) == ("0.00", "0")
    assert goals_row["player_a_is_better"] is True
    assert goals_row["player_b_is_better"] is False
    yellow_row = next(row for row in payload["rows"] if row["label"] == "Yellow cards per 90")
    # Ortegon: 1 yellow in 270 minutes. The unplayed side reads as 0.00, not as "no data".
    assert (yellow_row["player_a_per_ninety"], yellow_row["player_b_per_ninety"]) == (
        "0.33",
        "0.00",
    )
    assert outcome.widget_data is not None


async def test_goalkeeper_comparison_drops_the_rows_the_unmeasured_keeper_lacks(
    registry: dict[str, ToolDefinition],
) -> None:
    payload = (
        await call_tool(
            registry,
            _COMPARISON,
            player_a_name="Emilio Santorini",
            player_b_name="Zeno Quillfeather",
        )
    ).payload

    assert (payload["player_a"]["position"], payload["player_b"]["position"]) == ("GK", "GK")
    labels = {row["label"] for row in payload["rows"]}
    assert "Goals per 90" in labels
    assert labels.isdisjoint(_GOALKEEPER_ONLY_ROWS)


async def test_comparing_a_player_without_stats_in_first_position_names_that_player(
    registry: dict[str, ToolDefinition],
) -> None:
    outcome = await call_tool(
        registry, _COMPARISON, player_a_name="Nico Falkenrath", player_b_name="Rafael Ortegon"
    )

    assert outcome.payload == {"error": "No stats recorded for 'Nico Falkenrath'."}
    assert outcome.widget_data is None


async def test_when_both_players_lack_stats_the_first_one_is_reported(
    registry: dict[str, ToolDefinition],
) -> None:
    outcome = await call_tool(
        registry, _COMPARISON, player_a_name="Nico Falkenrath", player_b_name="Kestrel Dunmore"
    )

    assert outcome.payload == {"error": "No stats recorded for 'Nico Falkenrath'."}


async def test_unknown_player_is_reported_before_a_missing_stat_row(
    registry: dict[str, ToolDefinition],
) -> None:
    """Both names are resolved first, so an unknown second player hides the stat-less first."""
    outcome = await call_tool(
        registry, _COMPARISON, player_a_name="Nico Falkenrath", player_b_name=UNKNOWN_PLAYER
    )

    assert outcome.payload == {"error": UNKNOWN_PLAYER_ERROR}
    assert outcome.widget_data is None


async def test_unknown_first_player_is_the_one_named_in_the_error(
    registry: dict[str, ToolDefinition],
) -> None:
    outcome = await call_tool(
        registry, _COMPARISON, player_a_name=UNKNOWN_PLAYER, player_b_name="Rafael Ortegon"
    )

    assert outcome.payload == {"error": UNKNOWN_PLAYER_ERROR}
    assert outcome.widget_data is None


async def test_career_only_player_cannot_be_compared_because_comparison_has_no_career_fallback(
    registry: dict[str, ToolDefinition],
) -> None:
    outcome = await call_tool(
        registry, _COMPARISON, player_a_name="Anselmo Veridian", player_b_name="Rafael Ortegon"
    )

    assert outcome.payload == {"error": "No player found matching 'Anselmo Veridian'."}
    assert outcome.widget_data is None
