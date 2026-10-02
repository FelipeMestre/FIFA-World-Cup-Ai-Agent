"""Layer B golden cases for two-tool turns and the clock tool.

The clock case needs no fixture: it checks the tool is called and the answer carries the
current UTC date (yesterday, today or tomorrow, so a run across midnight UTC still passes).
The mixed cases need two different tools in one turn, with a fact from each in the answer.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.evals.grounding_harness import ObservedTurn
from tests.golden import expected, fixture_data, fixture_matches
from tests.golden import llm_facts as facts
from tests.golden.llm_assertions import (
    assert_mentions_names,
    assert_mentions_numbers,
    assert_tool_called,
    mentions_date,
    mentions_number,
    mentions_score,
)
from tests.golden.llm_cases import GoldenLlmCase, run_golden_case

pytestmark = pytest.mark.llm_eval

_MONTEFUSCO = facts.stat(fixture_data.MONTEFUSCO_ID)
_GROUP = facts.match(fixture_matches.GROUP_VLD_KRS_ID)


def _states_current_utc_date(turn: ObservedTurn) -> None:
    assert_tool_called(turn, "get_current_utc_time")
    today = datetime.now(UTC).date()
    plausible_days = [today + timedelta(days=offset) for offset in (-1, 0, 1)]
    assert any(mentions_date(turn.answer, day) for day in plausible_days), (
        f"answer carries no date near {today}"
    )


def _team_goals_and_player_minutes(turn: ObservedTurn) -> None:
    assert_tool_called(turn, "get_team_analysis")
    assert_tool_called(turn, "get_player_analysis")
    assert_mentions_numbers(
        turn, [expected.VALDORIA_RECORD["goals_for"], _MONTEFUSCO.minutes_played], "the"
    )


def _group_score_and_karsovia_goals_conceded(turn: ObservedTurn) -> None:
    assert_tool_called(turn, "get_match_analysis")
    assert_tool_called(turn, "get_team_analysis")
    assert mentions_score(turn.answer, _GROUP.home_score, _GROUP.away_score)
    assert mentions_number(turn.answer, expected.KARSOVIA_RECORD["goals_against"])


def _team_comparison_and_player_goals(turn: ObservedTurn) -> None:
    assert_tool_called(turn, "get_team_comparison")
    assert_tool_called(turn, "get_player_analysis")
    assert_mentions_names(turn, [expected.VALDORIA_TOP_SCORER])
    assert_mentions_numbers(turn, [facts.stat(fixture_data.ORTEGON_ID).goals], "Ortegon's goals")


CASES = [
    GoldenLlmCase(
        "clock-current-utc-date",
        "What is today's date and the current time in UTC?",
        _states_current_utc_date,
    ),
    GoldenLlmCase(
        "mixed-team-goals-and-player-minutes",
        "How many goals has Valdoria scored at the World Cup, and how many minutes has "
        "Dario Montefusco played?",
        _team_goals_and_player_minutes,
    ),
    GoldenLlmCase(
        "mixed-match-score-and-team-record",
        "What was the score of the Valdoria-Karsovia group game, and how many goals has "
        "Karsovia conceded in the whole tournament?",
        _group_score_and_karsovia_goals_conceded,
    ),
    GoldenLlmCase(
        "mixed-team-comparison-and-player",
        "Compare Valdoria and Karsovia as teams, and also tell me how many goals Rafael "
        "Ortegon has scored.",
        _team_comparison_and_player_goals,
    ),
]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.case_id)
async def test_multi_tool_golden_case(golden_session: AsyncSession, case: GoldenLlmCase) -> None:
    await run_golden_case(golden_session, case)
