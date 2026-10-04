"""No-data cases for `get_match_analysis`.

Unknown team, teams that never met, and a stage or date matching nothing are already pinned
in `test_match_analysis.py`; this module adds the match that exists with nothing recorded
(a scheduled fixture), the teams that have no matches at all, and the malformed selectors
(see `no_data_cases` for the whole map).
"""

import pytest

from src.domain.chat.tools.registry import ToolDefinition
from tests.golden import expected
from tests.golden.fixture_empty import SCHEDULED_VRN_QLS_ID
from tests.golden.no_data_cases import UNKNOWN_TEAM
from tests.golden.tools import call_tool

_TOOL = "get_match_analysis"
_STAT_LABELS = ["Possession", "Shots", "On target", "Corners", "Fouls", "Offsides"]
_EVEN_SPLIT_PCT = 50


async def test_scheduled_match_with_no_events_stats_or_lineups_yields_empty_sections(
    registry: dict[str, ToolDefinition],
) -> None:
    outcome = await call_tool(registry, _TOOL, home_team_name="Varnholm", away_team_name="Quellis")

    payload = outcome.payload
    assert payload["id"] == str(SCHEDULED_VRN_QLS_ID)
    assert (payload["home_team"]["code"], payload["away_team"]["code"]) == ("VRN", "QLS")
    assert payload["status_label"] == "Scheduled"
    assert payload["stage_label"] == "Group Stage"
    assert payload["date_label"] == "Jul 1, 2026"
    assert payload["home_scorers"] == ""
    assert payload["away_scorers"] == ""
    assert payload["events"] == []
    assert payload["timeline"] == []
    assert payload["footer_caption"] == "0 goals"
    assert outcome.widget_data is not None


async def test_match_without_team_stats_shows_zero_values_and_an_even_split(
    registry: dict[str, ToolDefinition],
) -> None:
    payload = (await call_tool(registry, _TOOL, home_team_name="VRN", away_team_name="QLS")).payload

    assert [row["label"] for row in payload["stats"]] == _STAT_LABELS
    for row in payload["stats"]:
        assert row["home_pct"] == _EVEN_SPLIT_PCT
        assert row["home_value"].rstrip("%") == "0"
        assert row["away_value"].rstrip("%") == "0"


async def test_match_without_lineups_returns_both_teams_with_no_players(
    registry: dict[str, ToolDefinition],
) -> None:
    payload = (await call_tool(registry, _TOOL, home_team_name="VRN", away_team_name="QLS")).payload

    assert [(lineup["code"], lineup["groups"]) for lineup in payload["lineups"]] == [
        ("VRN", []),
        ("QLS", []),
    ]
    assert {lineup["shape"] for lineup in payload["lineups"]} == {"0-0-0"}


async def test_player_of_the_match_is_always_present_even_when_nothing_happened(
    registry: dict[str, ToolDefinition],
) -> None:
    """The schema makes the Player of the Match a required foreign key, so the 'Unknown'
    placeholder branch of the repository cannot be reached with real rows."""
    payload = (await call_tool(registry, _TOOL, home_team_name="VRN", away_team_name="QLS")).payload

    potm = payload["player_of_match"]
    assert (potm["name"], potm["team_code"], potm["position"]) == ("Kestrel Dunmore", "VRN", "DEF")
    assert potm["note"] == "Varnholm · DEF · 0 goals"


async def test_scheduled_match_is_oriented_by_the_recorded_fixture_not_the_query(
    registry: dict[str, ToolDefinition],
) -> None:
    payload = (
        await call_tool(registry, _TOOL, home_team_name="Quellis", away_team_name="Varnholm")
    ).payload

    assert (payload["home_team"]["code"], payload["away_team"]["code"]) == ("VRN", "QLS")


@pytest.mark.parametrize(
    ("home", "away"),
    [
        ("Ostravia", "Thalmoor"),
        ("Valdoria", "Valdoria"),
        (UNKNOWN_TEAM, "Valdoria"),
        (UNKNOWN_TEAM, UNKNOWN_TEAM),
    ],
    ids=["teams-without-matches", "same-team-twice", "unknown-first-team", "both-unknown"],
)
async def test_pairs_that_cannot_have_a_match_return_the_not_found_error_without_widget(
    registry: dict[str, ToolDefinition], home: str, away: str
) -> None:
    outcome = await call_tool(registry, _TOOL, home_team_name=home, away_team_name=away)

    assert outcome.payload == {"error": f"No match found between '{home}' and '{away}'."}
    assert outcome.widget_data is None


@pytest.mark.parametrize(
    "selector",
    [{"stage": ""}, {"date": ""}, {"stage": "", "date": ""}],
    ids=["empty-stage", "empty-date", "both-empty"],
)
async def test_empty_string_selectors_are_ignored_and_the_repeat_fixture_stays_ambiguous(
    registry: dict[str, ToolDefinition], selector: dict
) -> None:
    outcome = await call_tool(
        registry, _TOOL, home_team_name="Valdoria", away_team_name="Karsovia", **selector
    )

    ids = [row["id"] for row in outcome.payload["candidates"]]
    assert ids == [expected.GROUP_VLD_KRS_ID, expected.FINAL_KRS_VLD_ID]
    assert outcome.widget_data is None


@pytest.mark.parametrize("bad_date", ["June 14", "14/06/2026", "2026-13-40", "2026-06-14T18:00"])
async def test_malformed_date_raises_value_error_instead_of_returning_a_tool_error(
    registry: dict[str, ToolDefinition], bad_date: str
) -> None:
    """Today's behavior, reported as a finding: the date string is parsed with
    `date.fromisoformat` and nothing catches the `ValueError`, so the tool never answers
    with `{"error": ...}` for a date the model formatted wrongly."""
    with pytest.raises(ValueError):
        await call_tool(
            registry,
            _TOOL,
            home_team_name="Valdoria",
            away_team_name="Karsovia",
            date=bad_date,
        )
