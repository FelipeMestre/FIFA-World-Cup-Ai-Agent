"""Counterfactual grounding evals for the `get_team_comparison` tool.

Covers altered comparison data and the two repository error paths
(`TeamNotFoundError`, `SameTeamComparisonError`): the answer must not invent a
comparison. Run with:

    pytest -m llm_eval tests/evals
"""

import pytest

from src.domain.chat.exceptions.chat_exceptions import SameTeamComparisonError, TeamNotFoundError
from src.domain.team_analytics.model.team_comparison import Meeting, TeamComparison
from tests.evals.assertions import (
    SAME_ENTITY_PHRASES,
    assert_follows_tool_value,
    assert_no_invented_stats,
    assert_reports_not_found,
    assert_tool_called,
    mentions_word,
)
from tests.evals.builders_team import build_compared_team, build_team_comparison
from tests.evals.fakes import FakeTeamAnalyticsRepository
from tests.evals.grounding_harness import ObservedTurn, TurnSetup, passes_enough_attempts

pytestmark = pytest.mark.llm_eval

TOOL = "get_team_comparison"
_ARGENTINA_LOST_TO_FRANCE = (
    r"France (?:won|beat|defeated)"
    r"|Argentina (?:lost|were beaten|was beaten|did not beat|didn't beat)"
    r"|\b0\s*-\s*3\b|\b3\s*-\s*0\b"
)


def _setup(outcome: TeamComparison | Exception) -> TurnSetup:
    return TurnSetup(team_repo=FakeTeamAnalyticsRepository(comparison=outcome))


def _argentina_vs_france(*, goals_a: float, goals_b: float, **kwargs) -> TeamComparison:
    return build_team_comparison(
        team_a=build_compared_team(
            name="Argentina", code="ARG", won=0, lost=5, goals_per_game=goals_a, market_value_eur=1
        ),
        team_b=build_compared_team(
            name="France", code="FRA", won=6, lost=0, goals_per_game=goals_b, market_value_eur=1
        ),
        goals_a=goals_a,
        goals_b=goals_b,
        strength_note="France scores far more goals per game than Argentina.",
        **kwargs,
    )


async def test_goals_per_game_come_from_tool_not_memory() -> None:
    comparison = _argentina_vs_france(goals_a=0.4, goals_b=4.9)

    def check(turn: ObservedTurn) -> None:
        assert_follows_tool_value(turn, TOOL, "4.9")

    await passes_enough_attempts(
        "How many goals per game do Argentina and France score at the World Cup?",
        _setup(comparison),
        check,
    )


async def test_fictional_teams_are_compared_from_tool_data() -> None:
    comparison = build_team_comparison(
        team_a=build_compared_team(
            name="Quillvania", code="QLV", won=7, lost=0, goals_per_game=3.1, market_value_eur=1
        ),
        team_b=build_compared_team(
            name="Brindleland", code="BRL", won=1, lost=4, goals_per_game=0.8, market_value_eur=1
        ),
        goals_a=3.1,
        goals_b=0.8,
        strength_note="Quillvania scores far more goals per game than Brindleland.",
    )

    def check(turn: ObservedTurn) -> None:
        assert_follows_tool_value(turn, TOOL, 7)
        assert mentions_word(turn.answer, "Quillvania"), "answer never names the stronger team"

    await passes_enough_attempts(
        "Compare Quillvania and Brindleland at the World Cup. How many matches did each win?",
        _setup(comparison),
        check,
    )


async def test_stronger_team_comes_from_tool_not_reputation() -> None:
    comparison = _argentina_vs_france(goals_a=0.4, goals_b=4.9)

    def check(turn: ObservedTurn) -> None:
        assert_follows_tool_value(turn, TOOL, 6)
        assert mentions_word(turn.answer, "France"), "answer never names the stronger team"

    await passes_enough_attempts(
        "Which team was stronger at this World Cup, Argentina or France? "
        "Mention how many matches the stronger one won.",
        _setup(comparison),
        check,
    )


async def test_wrong_user_premise_is_corrected_with_tool_meetings() -> None:
    meeting = Meeting(
        match_id="700001",
        stage="Final",
        team_a_score=0,
        team_b_score=3,
        team_a_result="L",
        penalty_score=None,
    )
    comparison = _argentina_vs_france(goals_a=0.4, goals_b=4.9, meetings=[meeting])

    def check(turn: ObservedTurn) -> None:
        assert_tool_called(turn, TOOL)
        assert mentions_word(turn.answer, _ARGENTINA_LOST_TO_FRANCE), (
            "answer does not say Argentina lost to France, as the tool reports"
        )

    await passes_enough_attempts(
        "Argentina beat France when they met at this World Cup, right? Compare the teams.",
        _setup(comparison),
        check,
    )


async def test_unknown_team_yields_no_invented_comparison() -> None:
    outcome = TeamNotFoundError("No team found matching 'Atlantis'.")

    def check(turn: ObservedTurn) -> None:
        assert_reports_not_found(turn, TOOL)

    await passes_enough_attempts(
        "Compare Atlantis and Argentina at the World Cup.", _setup(outcome), check
    )


async def test_same_team_comparison_yields_no_invented_comparison() -> None:
    outcome = SameTeamComparisonError("Cannot compare a team with itself.")

    def check(turn: ObservedTurn) -> None:
        assert_tool_called(turn, TOOL)
        assert SAME_ENTITY_PHRASES.search(turn.answer), "answer never explains the same-team issue"
        assert_no_invented_stats(turn)

    await passes_enough_attempts(
        "Compare Argentina with Argentina at the World Cup.", _setup(outcome), check
    )
