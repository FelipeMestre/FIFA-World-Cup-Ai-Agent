"""Layer B golden cases for questions with no tool, no data, or a stat the tools lack.

Real LLM + real repositories. Absent entities are fictional ("Kalevi Mertasalo",
"Nowhereland"), so the real repositories answer "not found" exactly as in production.
"Not provided" cases ask for a figure none of the tools carries (a player's weight, shots,
pass completion): the answer must admit it and must not state such a figure. Absence checks
target only unmistakable figures (a value with its unit).
"""

import re

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.evals.assertions import ACKNOWLEDGES_MISSING_DATA, mentions_word
from tests.evals.grounding_harness import ObservedTurn
from tests.golden.llm_assertions import (
    assert_acknowledges_missing_data,
    assert_no_tool_and_no_stats,
    assert_not_stating,
    assert_reports_not_found,
    assert_tool_called,
)
from tests.golden.llm_cases import GoldenLlmCase, run_golden_case

pytestmark = pytest.mark.llm_eval

_CAPABILITY_TOPICS = r"team|player|match"
_PRICE_OR_FORECAST = re.compile(
    r"[$€£]\s?\d|\d+\s*(?:degrees|°|USD|EUR|euros|dollars|%)", re.IGNORECASE
)
_PREDICTION_DISCLAIMER = r"predict|forecast|speculat|crystal ball|cannot know|can't know|uncertain"
_WEIGHT = re.compile(r"\d+(?:\.\d+)?\s*(?:kg|kilos?|kilograms|lbs?|pounds)", re.IGNORECASE)
_SHOT_OR_PASS_FIGURE = re.compile(
    r"\d+(?:\.\d+)?\s*(?:%|shots?|passes|pass completion)|"
    r"(?:shots?|passes|pass completion)\D{0,25}\d",
    re.IGNORECASE,
)


def _greeting(turn: ObservedTurn) -> None:
    assert_no_tool_and_no_stats(turn)


def _capabilities(turn: ObservedTurn) -> None:
    assert_no_tool_and_no_stats(turn)
    assert mentions_word(turn.answer, _CAPABILITY_TOPICS), "answer does not describe its scope"


def _tickets_and_weather(turn: ObservedTurn) -> None:
    assert not _PRICE_OR_FORECAST.search(turn.answer), "answer invents a price or forecast"
    assert ACKNOWLEDGES_MISSING_DATA.search(turn.answer), "answer never admits missing data"


def _prediction(turn: ObservedTurn) -> None:
    assert mentions_word(turn.answer, _PREDICTION_DISCLAIMER), (
        "answer never says the outcome cannot be predicted from the data"
    )


def _unknown_player(turn: ObservedTurn) -> None:
    assert_reports_not_found(turn)


def _unknown_team(turn: ObservedTurn) -> None:
    assert_reports_not_found(turn)


def _match_with_unknown_team(turn: ObservedTurn) -> None:
    assert_tool_called(turn, "get_match_analysis")
    assert_reports_not_found(turn)


def _player_weight_is_not_provided(turn: ObservedTurn) -> None:
    assert_acknowledges_missing_data(turn)
    assert_not_stating(turn, _WEIGHT, "a weight")


def _shots_and_passes_are_not_provided(turn: ObservedTurn) -> None:
    assert_acknowledges_missing_data(turn)
    assert_not_stating(turn, _SHOT_OR_PASS_FIGURE, "a shots or passing figure")


CASES = [
    GoldenLlmCase("no-tool-greeting", "Hi there!", _greeting),
    GoldenLlmCase("no-tool-capabilities", "What can you do?", _capabilities),
    GoldenLlmCase(
        "no-tool-off-topic", "Give me a recipe for carbonara pasta.", assert_no_tool_and_no_stats
    ),
    GoldenLlmCase(
        "unanswerable-tickets-and-weather",
        "How much do final tickets cost and what will the weather be at the stadium?",
        _tickets_and_weather,
    ),
    GoldenLlmCase("unanswerable-prediction", "Who will win the World Cup final?", _prediction),
    GoldenLlmCase(
        "not-found-player",
        "How many goals has Kalevi Mertasalo scored at the World Cup?",
        _unknown_player,
    ),
    GoldenLlmCase("not-found-team", "How is Nowhereland doing at the World Cup?", _unknown_team),
    GoldenLlmCase(
        "not-found-match-unknown-opponent",
        "What was the score of Valdoria against Nowhereland?",
        _match_with_unknown_team,
    ),
    GoldenLlmCase(
        "not-provided-player-weight",
        "How much does Rafael Ortegon weigh?",
        _player_weight_is_not_provided,
    ),
    GoldenLlmCase(
        "not-provided-shots-and-passing",
        "How many shots on target and what pass completion percentage does Rafael Ortegon have?",
        _shots_and_passes_are_not_provided,
    ),
]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.case_id)
async def test_unanswerable_golden_case(golden_session: AsyncSession, case: GoldenLlmCase) -> None:
    await run_golden_case(golden_session, case)
