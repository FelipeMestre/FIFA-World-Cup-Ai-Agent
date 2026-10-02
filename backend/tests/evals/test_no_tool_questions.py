"""Grounding evals for questions that need no tool or that tools cannot answer.

Design: every repository is an empty fake (`FakeTeam/Player/MatchAnalytics`
with nothing configured), so a tool call returns the same "not found" /
"no players matched" payload a real empty database would. Raising fakes were
rejected on purpose: `ToolCallExecutor` does not catch handler exceptions, so a
`NotImplementedError` would crash the turn instead of reaching the model, and
the eval would test the harness rather than the model. Whether a tool is
called is asserted only where the prompt makes it deterministic (greeting,
capabilities, off-topic: no tool; a stats request: tool consulted).

In every case the answer must not state football statistics, which is the
signature of an answer invented from model memory. Run with:

    pytest -m llm_eval tests/evals
"""

import re

import pytest

from tests.evals.assertions import (
    ACKNOWLEDGES_MISSING_DATA,
    assert_no_invented_stats,
    mentions_word,
)
from tests.evals.fakes import (
    FakeMatchAnalyticsRepository,
    FakePlayerAnalyticsRepository,
    FakeTeamAnalyticsRepository,
)
from tests.evals.grounding_harness import ObservedTurn, TurnSetup, passes_enough_attempts

pytestmark = pytest.mark.llm_eval

_CAPABILITY_TOPICS = r"team|player|match"
_PRICE_OR_FORECAST = re.compile(
    r"[$€£]\s?\d|\d+\s*(?:degrees|°|USD|EUR|euros|dollars|%)", re.IGNORECASE
)
_PREDICTION_DISCLAIMER = r"predict|forecast|speculat|crystal ball|cannot know|can't know|uncertain"


def _empty_data_setup() -> TurnSetup:
    return TurnSetup(
        team_repo=FakeTeamAnalyticsRepository(),
        player_repo=FakePlayerAnalyticsRepository(),
        match_repo=FakeMatchAnalyticsRepository(),
    )


def _assert_no_tool_and_no_stats(turn: ObservedTurn) -> None:
    assert turn.tools_called == [], f"a tool was called unnecessarily: {turn.tools_called}"
    assert_no_invented_stats(turn)


async def test_greeting_needs_no_tool() -> None:
    await passes_enough_attempts("Hi there!", _empty_data_setup(), _assert_no_tool_and_no_stats)


async def test_capabilities_question_describes_scope_without_stats() -> None:
    def check(turn: ObservedTurn) -> None:
        _assert_no_tool_and_no_stats(turn)
        assert mentions_word(turn.answer, _CAPABILITY_TOPICS), "answer does not describe its scope"

    await passes_enough_attempts("What can you do?", _empty_data_setup(), check)


async def test_off_topic_request_gets_no_football_stats() -> None:
    await passes_enough_attempts(
        "Give me a recipe for carbonara pasta.", _empty_data_setup(), _assert_no_tool_and_no_stats
    )


async def test_question_tools_cannot_answer_does_not_invent_data() -> None:
    def check(turn: ObservedTurn) -> None:
        assert_no_invented_stats(turn)
        assert not _PRICE_OR_FORECAST.search(turn.answer), "answer invents a price or forecast"
        assert ACKNOWLEDGES_MISSING_DATA.search(turn.answer), "answer never admits missing data"

    await passes_enough_attempts(
        "How much do final tickets cost and what will the weather be at the stadium?",
        _empty_data_setup(),
        check,
    )


async def test_prediction_request_does_not_invent_stats_or_certainty() -> None:
    def check(turn: ObservedTurn) -> None:
        assert_no_invented_stats(turn)
        assert mentions_word(turn.answer, _PREDICTION_DISCLAIMER), (
            "answer never says the outcome cannot be predicted from the data"
        )

    await passes_enough_attempts("Who will win the World Cup final?", _empty_data_setup(), check)


async def test_stats_request_with_no_data_does_not_fall_back_to_memory() -> None:
    def check(turn: ObservedTurn) -> None:
        assert turn.tools_called, "model answered a stats request without consulting any tool"
        assert_no_invented_stats(turn)
        assert ACKNOWLEDGES_MISSING_DATA.search(turn.answer), "answer never admits missing data"

    await passes_enough_attempts(
        "Is Lionel Messi better than Cristiano Ronaldo? Give me numbers from the tournament.",
        _empty_data_setup(),
        check,
    )
