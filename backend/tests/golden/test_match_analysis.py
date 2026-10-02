"""Golden cases for `get_match_analysis`: single match, repeat fixtures, not-found."""

import pytest

from src.domain.chat.tools.registry import ToolDefinition
from tests.golden import expected
from tests.golden.tools import call_tool

_TOOL = "get_match_analysis"


async def test_single_match_is_oriented_by_the_recorded_fixture_not_the_query(
    registry: dict[str, ToolDefinition],
) -> None:
    """Sérvenia hosted Valdoria, but the user names Valdoria first."""
    outcome = await call_tool(registry, _TOOL, home_team_name="Valdoria", away_team_name="Sérvenia")

    payload = outcome.payload
    assert payload["id"] == expected.GROUP_SRV_VLD_ID
    assert (payload["home_team"]["code"], payload["away_team"]["code"]) == ("SRV", "VLD")
    assert (payload["home_score"], payload["away_score"]) == (0, 3)
    assert payload["stage_label"] == "Group Stage"
    assert payload["date_label"] == "Jun 20, 2026"
    assert payload["status_label"] == "Full time"
    assert payload["venue_label"] == "Estadio Fixture, Fixturia"
    assert payload["home_scorers"] == ""
    assert payload["away_scorers"] == expected.SERVENIA_VLD_AWAY_SCORERS
    assert payload["footer_caption"] == "3 goals"
    assert outcome.widget_data is not None


async def test_match_stats_are_split_between_the_recorded_sides(
    registry: dict[str, ToolDefinition],
) -> None:
    payload = (await call_tool(registry, _TOOL, home_team_name="SRV", away_team_name="VLD")).payload

    stats = {row["label"]: row for row in payload["stats"]}
    assert (stats["Possession"]["home_value"], stats["Possession"]["away_value"]) == ("40%", "60%")
    assert stats["Possession"]["home_pct"] == 40
    assert (stats["Shots"]["home_value"], stats["Shots"]["away_value"]) == ("5", "16")
    assert (stats["Fouls"]["home_value"], stats["Fouls"]["away_value"]) == ("14", "7")


async def test_player_of_the_match_names_player_team_and_goal_count(
    registry: dict[str, ToolDefinition],
) -> None:
    payload = (await call_tool(registry, _TOOL, home_team_name="SRV", away_team_name="VLD")).payload

    potm = payload["player_of_match"]
    assert (potm["name"], potm["team_code"], potm["position"]) == ("Dario Montefusco", "VLD", "FWD")
    assert potm["note"] == "Valdoria · FWD · 1 goal"


async def test_two_matches_between_the_same_teams_return_a_candidate_list_without_widget(
    registry: dict[str, ToolDefinition],
) -> None:
    outcome = await call_tool(registry, _TOOL, home_team_name="Valdoria", away_team_name="Karsovia")

    candidates = [
        (
            row["id"],
            row["stage_label"],
            row["date_label"],
            row["home_team_code"],
            row["away_team_code"],
            row["score"],
        )
        for row in outcome.payload["candidates"]
    ]
    assert candidates == expected.AMBIGUOUS_CANDIDATES
    assert outcome.widget_data is None


@pytest.mark.parametrize(
    ("selector", "expected_match_id"),
    [
        ({"stage": "Group Stage"}, expected.GROUP_VLD_KRS_ID),
        ({"stage": "group"}, expected.GROUP_VLD_KRS_ID),
        ({"stage": "Final"}, expected.FINAL_KRS_VLD_ID),
        ({"date": "2026-06-14"}, expected.GROUP_VLD_KRS_ID),
        ({"date": "2026-07-19"}, expected.FINAL_KRS_VLD_ID),
        ({"stage": "Final", "date": "2026-07-19"}, expected.FINAL_KRS_VLD_ID),
    ],
    ids=["stage", "stage-substring", "final", "date-group", "date-final", "stage-and-date"],
)
async def test_stage_or_date_resolves_the_repeat_fixture(
    registry: dict[str, ToolDefinition], selector: dict, expected_match_id: str
) -> None:
    outcome = await call_tool(
        registry, _TOOL, home_team_name="Valdoria", away_team_name="Karsovia", **selector
    )

    assert outcome.payload["id"] == expected_match_id
    assert outcome.widget_data is not None


async def test_group_stage_match_scorers_timeline_and_lineups(
    registry: dict[str, ToolDefinition],
) -> None:
    payload = (
        await call_tool(registry, _TOOL, home_team_name="VLD", away_team_name="KRS", stage="Group")
    ).payload

    assert (payload["home_scorers"], payload["away_scorers"]) == expected.GROUP_VLD_KRS_SCORERS
    first_goal = next(event for event in payload["timeline"] if event["kind"] == "goal")
    assert first_goal["minute"] == "23'"
    assert first_goal["detail"] == "Assist Dario Montefusco"
    cards = [event for event in payload["timeline"] if event["kind"] == "card"]
    assert [(card["team_code"], card["title"]) for card in cards] == [
        ("VLD", "Yellow Card · Tomás Peñaranda")
    ]
    valdoria_lineup = next(lineup for lineup in payload["lineups"] if lineup["code"] == "VLD")
    groups = {
        group["name"]: [p["name"] for p in group["players"]] for group in valdoria_lineup["groups"]
    }
    assert groups["GK"] == ["Emilio Santorini"]
    assert groups["Subs used"] == ["Dario Montefusco"]
    assert payload["player_of_match"]["name"] == "Rafael Ortegon"
    assert payload["player_of_match"]["note"] == "Valdoria · FWD · 2 goals"


async def test_final_decided_on_penalties_is_labelled_and_lists_the_goalkeeper_potm(
    registry: dict[str, ToolDefinition],
) -> None:
    payload = (
        await call_tool(registry, _TOOL, home_team_name="VLD", away_team_name="KRS", stage="Final")
    ).payload

    assert payload["status_label"] == "Full time (pens)"
    assert (payload["home_team"]["code"], payload["away_team"]["code"]) == ("KRS", "VLD")
    assert (payload["home_score"], payload["away_score"]) == (1, 1)
    assert (payload["home_scorers"], payload["away_scorers"]) == expected.FINAL_SCORERS
    assert payload["player_of_match"]["name"] == "Pavel Kozhukar"
    assert payload["player_of_match"]["note"] == "Karsovia · GK · 0 goals"
    assert payload["footer_caption"] == "2 goals · 2 cards"
    assert payload["home_team"]["name"] == "Karsovia"


@pytest.mark.parametrize(
    ("home", "away", "selector"),
    [
        ("Valdoria", "Nowhereland", {}),
        ("Karsovia", "Sérvenia", {}),
        ("Valdoria", "Sérvenia", {"stage": "Final"}),
        ("Valdoria", "Karsovia", {"date": "2026-01-01"}),
    ],
    ids=["unknown-team", "teams-never-met", "stage-without-match", "date-without-match"],
)
async def test_no_matching_fixture_returns_not_found_error_without_widget(
    registry: dict[str, ToolDefinition], home: str, away: str, selector: dict
) -> None:
    outcome = await call_tool(registry, _TOOL, home_team_name=home, away_team_name=away, **selector)

    assert outcome.payload == {"error": f"No match found between '{home}' and '{away}'."}
    assert outcome.widget_data is None
