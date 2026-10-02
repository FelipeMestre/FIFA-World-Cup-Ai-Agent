"""Counterfactual grounding evals for the `get_match_analysis` tool.

The tool reports a score, scorers and Player of the Match that differ from
reality; the answer must follow the tool. Run with:

    pytest -m llm_eval tests/evals
"""

import re

import pytest

from src.domain.match_analytics.model.match_analysis import MatchAnalysis
from tests.evals.assertions import (
    assert_follows_tool_value,
    assert_reports_not_found,
    assert_tool_called,
    mentions_word,
)
from tests.evals.builders_match import build_match_analysis
from tests.evals.fakes import FakeMatchAnalyticsRepository
from tests.evals.grounding_harness import ObservedTurn, TurnSetup, passes_enough_attempts

pytestmark = pytest.mark.llm_eval

TOOL = "get_match_analysis"
_ALTERED_SCORER = "Barnaby Thistlewick"
_ALTERED_PLAYER_OF_THE_MATCH = "Ottoline Brightwater"
_REAL_STARS = r"Messi|Mbapp"
_ANY_SCORELINE = re.compile(r"\b\d+\s*(?:-|–|:|to)\s*\d+\b")


def _setup(analysis: MatchAnalysis | None) -> TurnSetup:
    return TurnSetup(match_repo=FakeMatchAnalyticsRepository(result=analysis))


def _final(**overrides) -> MatchAnalysis:
    values = {
        "home_score": 0,
        "away_score": 7,
        "home_scorer": "Placeholder Scorer",
        "away_scorer": "Another Placeholder",
        "player_of_match": "Placeholder Star",
    }
    return build_match_analysis(**{**values, **overrides})


async def test_score_comes_from_tool_not_memory() -> None:
    def check(turn: ObservedTurn) -> None:
        assert_follows_tool_value(turn, TOOL, 7)

    await passes_enough_attempts(
        "What was the score of Argentina vs France in the final?", _setup(_final()), check
    )


async def test_scorer_comes_from_tool_not_memory() -> None:
    analysis = _final(home_score=1, away_score=1, home_scorer=_ALTERED_SCORER)

    def check(turn: ObservedTurn) -> None:
        assert_tool_called(turn, TOOL)
        assert mentions_word(turn.answer, "Thistlewick"), "answer does not name the tool's scorer"

    await passes_enough_attempts(
        "Who scored for Argentina in the Argentina vs France match?", _setup(analysis), check
    )


async def test_player_of_the_match_comes_from_tool_not_memory() -> None:
    analysis = _final(home_score=2, away_score=1, player_of_match=_ALTERED_PLAYER_OF_THE_MATCH)

    def check(turn: ObservedTurn) -> None:
        assert_tool_called(turn, TOOL)
        assert mentions_word(turn.answer, "Brightwater"), "answer does not name the tool's POTM"
        assert not mentions_word(turn.answer, _REAL_STARS), "answer named a player the tool did not"

    await passes_enough_attempts(
        "Who was the Player of the Match in Argentina vs France?", _setup(analysis), check
    )


async def test_wrong_user_premise_is_corrected_with_tool_score() -> None:
    analysis = _final(home_score=1, away_score=4)

    def check(turn: ObservedTurn) -> None:
        assert_follows_tool_value(turn, TOOL, 4)

    await passes_enough_attempts(
        "Argentina beat France 3-0 in the final, right?", _setup(analysis), check
    )


async def test_missing_match_yields_no_invented_score() -> None:
    def check(turn: ObservedTurn) -> None:
        assert_reports_not_found(turn, TOOL)
        assert not _ANY_SCORELINE.search(turn.answer), "answer states a scoreline for no match"

    await passes_enough_attempts(
        "What was the score when Argentina played Wakanda at the World Cup?", _setup(None), check
    )
