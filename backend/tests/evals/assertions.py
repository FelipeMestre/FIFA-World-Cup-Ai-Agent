"""Shared assertion helpers for the grounding evals.

Number checks use boundaries so `47` never matches inside `147` or `4.7`.
Phrase checks accept several natural wordings: they exist to catch a missing
behaviour, not to police the model's phrasing.
"""

import re

from tests.evals.grounding_harness import ObservedTurn

NOT_FOUND_PHRASES = re.compile(
    r"couldn't find|could not find|no player|no team|no match|not found|don't have|do not have|"
    r"no data|unable to find|no record|no information|can't find|cannot find|didn't find|"
    r"did not find|no results|wasn't able to find",
    re.IGNORECASE,
)

ACKNOWLEDGES_MISSING_DATA = re.compile(
    r"don't have|do not have|can't|cannot|unable|not available|no data|doesn't|does not|"
    r"isn't|is not|no information|not able|couldn't|could not|didn't|did not",
    re.IGNORECASE,
)

SAME_ENTITY_PHRASES = re.compile(
    r"same (?:player|team|person|one)|itself|themselves|himself|identical|two different|"
    r"cannot compare|can't compare|compare .* (?:with|to|against) (?:themselves|himself|itself)",
    re.IGNORECASE,
)

_FOOTBALL_STAT_UNITS = (
    r"goals?|assists?|matches|games|wins|losses|points|appearances|minutes|cards|clean sheets"
)
STAT_CLAIM = re.compile(rf"\b\d+(?:\.\d+)?\s+(?:{_FOOTBALL_STAT_UNITS})\b", re.IGNORECASE)


def mentions_value(text: str, value: int | float | str) -> bool:
    """True when `value` appears as a standalone token (not inside a longer number)."""
    return re.search(rf"(?<![\w.]){re.escape(str(value))}(?!\w)", text) is not None


def mentions_word(text: str, pattern: str) -> bool:
    return re.search(pattern, text, re.IGNORECASE) is not None


def assert_tool_called(turn: ObservedTurn, tool_name: str) -> None:
    assert tool_name in turn.tools_called, f"{tool_name} was never called"


def assert_follows_tool_value(turn: ObservedTurn, tool_name: str, value: int | float | str) -> None:
    assert_tool_called(turn, tool_name)
    assert mentions_value(turn.answer, value), f"answer does not report the tool's {value}"


def assert_no_invented_stats(turn: ObservedTurn) -> None:
    assert not STAT_CLAIM.search(turn.answer), "answer states a stat the tools never returned"


def assert_reports_not_found(turn: ObservedTurn, tool_name: str) -> None:
    assert_tool_called(turn, tool_name)
    assert NOT_FOUND_PHRASES.search(turn.answer), "answer never says nothing was found"
    assert_no_invented_stats(turn)
