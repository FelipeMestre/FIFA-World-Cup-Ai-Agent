"""Golden cases for `get_player_analysis`: name resolution, World Cup stats, club career."""

import pytest

from src.domain.chat.tools.registry import ToolDefinition
from tests.golden import expected, fixture_career, fixture_data
from tests.golden.tools import call_tool

_TOOL = "get_player_analysis"


@pytest.mark.parametrize(
    "query",
    ["Rafael Ortegon", "rafael ortegon", "Ortegon"],
    ids=["exact", "case-insensitive", "fuzzy-substring"],
)
async def test_world_cup_player_resolves_by_exact_and_fuzzy_name(
    registry: dict[str, ToolDefinition], query: str
) -> None:
    payload = (await call_tool(registry, _TOOL, player_name=query)).payload

    assert payload["id"] == str(fixture_data.ORTEGON_ID)
    assert payload["name"] == "Rafael Ortegon"
    assert payload["initials"] == "RO"


@pytest.mark.parametrize(
    "query",
    ["Tomás Peñaranda", "Tomas Penaranda", "Penaranda", "peñaranda"],
    ids=["accented-exact", "unaccented-exact", "unaccented-substring", "accented-substring"],
)
async def test_accented_player_name_resolves_with_or_without_accents(
    registry: dict[str, ToolDefinition], query: str
) -> None:
    payload = (await call_tool(registry, _TOOL, player_name=query)).payload

    assert payload["id"] == str(fixture_data.PENARANDA_ID)
    assert payload["name"] == "Tomás Peñaranda"
    assert payload["initials"] == "TP"


async def test_world_cup_totals_chips_and_per_90_for_an_outfield_player(
    registry: dict[str, ToolDefinition],
) -> None:
    payload = (await call_tool(registry, _TOOL, player_name="Rafael Ortegon")).payload

    assert payload["team_code"] == "VLD"
    assert payload["position"] == "FWD"
    assert (payload["appearances"], payload["minutes"]) == (3, 270)
    assert payload["scope_label"] == expected.ORTEGON_SCOPE_LABEL
    assert payload["footer_caption"] == expected.ORTEGON_FOOTER
    chips = {chip["label"]: chip["value"] for chip in payload["chips"]}
    assert (chips["Goals"], chips["Assists"]) == ("4", "1")
    goals_row = next(row for row in payload["full_breakdown"] if row["stat"] == "Goals")
    assert goals_row["total"] == "4"
    assert goals_row["per_ninety"] == expected.ORTEGON_GOALS_PER_90


async def test_goalkeeper_gets_goalkeeper_chips(registry: dict[str, ToolDefinition]) -> None:
    payload = (await call_tool(registry, _TOOL, player_name="Emilio Santorini")).payload

    assert payload["position"] == "GK"
    chips = {chip["label"]: chip["value"] for chip in payload["chips"]}
    for label, value in expected.SANTORINI_CHIPS.items():
        assert chips[label] == value


async def test_duplicate_name_silently_resolves_to_one_of_the_players(
    registry: dict[str, ToolDefinition],
) -> None:
    """Two 'Mateo Ravelli' exist (Valdoria DEF, Karsovia FW). The repository takes the first
    row with no ORDER BY and never flags the ambiguity to the model, so which one comes back
    is unspecified. This pins the shape of today's behavior: one player, no ambiguity payload.
    """
    outcome = await call_tool(registry, _TOOL, player_name="Mateo Ravelli")

    duplicate_ids = {str(fixture_data.RAVELLI_VLD_ID), str(fixture_data.RAVELLI_KRS_ID)}
    assert outcome.payload["id"] in duplicate_ids
    assert outcome.payload["team_code"] in {"VLD", "KRS"}
    assert "candidates" not in outcome.payload
    assert "error" not in outcome.payload


async def test_unknown_player_returns_not_found_error_without_widget(
    registry: dict[str, ToolDefinition],
) -> None:
    outcome = await call_tool(registry, _TOOL, player_name="Zzyzx Nobody")

    assert outcome.payload == {"error": "No player found matching 'Zzyzx Nobody'."}
    assert outcome.widget_data is None


async def test_roster_player_without_stats_or_career_is_reported_as_not_found(
    registry: dict[str, ToolDefinition],
) -> None:
    outcome = await call_tool(registry, _TOOL, player_name="Nico Falkenrath")

    assert outcome.payload == {"error": "No player found matching 'Nico Falkenrath'."}
    assert outcome.widget_data is None


async def test_roster_player_without_stats_falls_back_to_same_named_career(
    registry: dict[str, ToolDefinition],
) -> None:
    payload = (await call_tool(registry, _TOOL, player_name="Bruno Haldorsen")).payload

    assert payload["id"] == str(fixture_career.HALDORSEN_REAL_ID)
    assert payload["scope_label"] == "Club career · totals"
    assert payload["team_code"] == expected.HALDORSEN_TEAM_CODE
    totals = expected.HALDORSEN_CAREER_TOTALS
    assert (payload["appearances"], payload["minutes"]) == (
        totals["appearances"],
        totals["minutes"],
    )
    rows = {row["stat"]: row for row in payload["full_breakdown"]}
    assert rows["Goals"]["total"] == totals["goals"]
    assert rows["Assists"]["total"] == totals["assists"]
    assert rows["Goals"]["percentile"] is None
    assert payload["per_ninety_vs_position_average"] == []


async def test_approved_identity_link_attaches_club_profile_transfers_and_seasons(
    registry: dict[str, ToolDefinition],
) -> None:
    payload = (await call_tool(registry, _TOOL, player_name="Rafael Ortegon")).payload

    profile = payload["club_profile"]
    for field, value in expected.ORTEGON_CLUB_PROFILE.items():
        assert profile[field] == value
    assert profile["date_of_birth"] == "1999-03-12"
    assert [move["transfer_date"] for move in payload["transfers"]] == (
        expected.ORTEGON_TRANSFER_DATES
    )
    assert payload["transfers"][1]["fee_eur"] == 20_000_000
    seasons = {
        (row["season"], row["competition"]): (row["team"], row["appearances"], row["goals"])
        for row in payload["career_seasons"]
    }
    assert seasons == expected.ORTEGON_CAREER_SEASONS


async def test_pending_identity_link_does_not_attach_club_profile(
    registry: dict[str, ToolDefinition],
) -> None:
    payload = (await call_tool(registry, _TOOL, player_name="Dario Montefusco")).payload

    assert payload["club_profile"] is None
    assert payload["transfers"] == []
    assert payload["career_seasons"] == []


async def test_player_who_never_played_the_world_cup_gets_career_totals_and_club_as_team(
    registry: dict[str, ToolDefinition],
) -> None:
    payload = (await call_tool(registry, _TOOL, player_name="Anselmo Veridian")).payload

    assert payload["scope_label"] == "Club career · totals"
    assert payload["team_code"] == expected.VERIDIAN_TEAM_CODE
    assert payload["tier_label"] == "Club career"
    assert payload["club_profile"]["is_retired"] is False


async def test_career_only_player_with_old_last_season_is_flagged_retired(
    registry: dict[str, ToolDefinition],
) -> None:
    payload = (await call_tool(registry, _TOOL, player_name="Casimir Orlowski")).payload

    assert payload["team_code"] == expected.RETIRED_TEAM_CODE
    assert payload["club_profile"]["is_retired"] is True
    assert payload["club_profile"]["current_club"] is None


async def test_career_only_player_without_a_club_gets_the_free_team_code(
    registry: dict[str, ToolDefinition],
) -> None:
    payload = (await call_tool(registry, _TOOL, player_name="Teodor Banerjee")).payload

    assert payload["team_code"] == expected.FREE_AGENT_TEAM_CODE
    assert payload["club_profile"]["is_retired"] is False
    assert payload["club_profile"]["current_club"] is None
