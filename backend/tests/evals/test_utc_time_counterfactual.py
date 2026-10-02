"""Counterfactual grounding evals for the `get_current_utc_time` tool.

The clock tool is static (no repository), so it is made counterfactual by
replacing its registry entry with a `ToolDefinition` that keeps the real
schema and args model but returns a fixed fake timestamp. The answer must use
that timestamp, not the model's guess about today's date. Run with:

    pytest -m llm_eval tests/evals
"""

import pytest

from src.domain.chat.tools.get_current_utc_time import (
    GET_CURRENT_UTC_TIME_SCHEMA,
    GetCurrentUtcTimeArgs,
)
from src.domain.chat.tools.registry import ToolDefinition
from src.domain.chat.tools.tool_execution_result import ToolExecutionResult
from tests.evals.assertions import assert_follows_tool_value, assert_tool_called, mentions_word
from tests.evals.grounding_harness import ObservedTurn, TurnSetup, passes_enough_attempts

pytestmark = pytest.mark.llm_eval

TOOL = "get_current_utc_time"
FAKE_TIMESTAMP = "2031-03-14T09:26:00Z"
FAKE_YEAR = 2031
_FAKE_CLOCK_TIME = r"\b0?9:26\b"
_FAKE_CLOCK_DATE = r"2031-03-14|March 14|14 March|14th of March|03/14/2031|14/03/2031"


async def _fake_clock_handler(_args: GetCurrentUtcTimeArgs) -> ToolExecutionResult:
    return ToolExecutionResult(content=FAKE_TIMESTAMP)


def _fake_clock_setup() -> TurnSetup:
    fake_clock = ToolDefinition(
        json_schema=GET_CURRENT_UTC_TIME_SCHEMA,
        args_model=GetCurrentUtcTimeArgs,
        handler=_fake_clock_handler,
    )
    return TurnSetup(registry_overrides={TOOL: fake_clock})


async def test_full_timestamp_comes_from_tool_not_guess() -> None:
    def check(turn: ObservedTurn) -> None:
        assert_follows_tool_value(turn, TOOL, FAKE_YEAR)
        assert mentions_word(turn.answer, _FAKE_CLOCK_TIME), "answer omits the tool's 09:26"
        assert mentions_word(turn.answer, _FAKE_CLOCK_DATE), "answer omits the tool's date"

    await passes_enough_attempts(
        "What is the current UTC date and time?", _fake_clock_setup(), check
    )


async def test_year_comes_from_tool_not_guess() -> None:
    def check(turn: ObservedTurn) -> None:
        assert_follows_tool_value(turn, TOOL, FAKE_YEAR)

    await passes_enough_attempts("What year is it right now?", _fake_clock_setup(), check)


async def test_wrong_user_premise_is_corrected_with_tool_time() -> None:
    def check(turn: ObservedTurn) -> None:
        assert_tool_called(turn, TOOL)
        assert mentions_word(turn.answer, str(FAKE_YEAR)), "answer keeps the user's wrong year"

    await passes_enough_attempts(
        "It is 2024 right now, correct? Check the clock and tell me today's date.",
        _fake_clock_setup(),
        check,
    )
