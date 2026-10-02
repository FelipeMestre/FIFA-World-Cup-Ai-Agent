"""Phrasing-robust assertion helpers for the Layer B golden cases.

Facts come from the fixture modules, never retyped. Matching is boundary-aware (`4` never
matches inside `147` or `4.7`), accent- and case-insensitive for names, and accepts the
usual spellings of scores, money and small numbers. Absence checks are reserved for
values that would be an unambiguous contradiction of the fixture.
"""

import re
import unicodedata
from collections.abc import Callable, Collection, Iterable
from datetime import date

from tests.evals.assertions import (
    ACKNOWLEDGES_MISSING_DATA,
    NOT_FOUND_PHRASES,
    assert_no_invented_stats,
)
from tests.evals.grounding_harness import ObservedTurn, ToolInvocation

_NUMBER_WORDS = [
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
    "twenty",
]
_SCORE_SEPARATOR = r"\s*(?:-|–|—|:|to)\s*"
ASKS_WHICH_ONE = re.compile(
    r"which (?:one|player|mateo)|do you mean|did you mean|could you (?:clarify|specify)|"
    r"can you (?:clarify|specify)|more (?:information|details|context)|more than one|"
    r"multiple|several|two (?:players|different)|narrow|specify|clarify",
    re.IGNORECASE,
)


def fold(text: str) -> str:
    """Lowercase and strip accents so 'Sérvenia' equals 'servenia'."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def number_forms(value: int) -> list[str]:
    forms = [str(value)]
    if 0 <= value < len(_NUMBER_WORDS):
        forms.append(_NUMBER_WORDS[value])
    return forms


def mentions_number(text: str, value: int) -> bool:
    """The number as digits (ordinals like '7th' too) or as an English word, standalone."""
    pattern = r"(?<![\w.]){form}(?:st|nd|rd|th)?(?!\w|\.\d)"
    return any(
        re.search(pattern.format(form=form), text, re.IGNORECASE) for form in number_forms(value)
    )


def mentions_count_of(text: str, value: int, noun_pattern: str) -> bool:
    """`value` right before a noun, e.g. '4 goals', 'four goals' or '4 league goals'."""
    for form in number_forms(value):
        before_noun = rf"(?<![\w.]){form}(?:\s+\w+)?\s+(?:{noun_pattern})"
        if re.search(before_noun, text, re.IGNORECASE):
            return True
    return False


def mentions_score(text: str, first: int, second: int) -> bool:
    """'2-1', '2–1', '2 - 1' or '2 to 1', in either orientation."""
    for left, right in ((first, second), (second, first)):
        if re.search(rf"(?<![\w.]){left}{_SCORE_SEPARATOR}{right}(?!\w)", text, re.IGNORECASE):
            return True
    return False


def mentions_name(text: str, full_name: str) -> bool:
    """The surname (last token), accent- and case-insensitive: 'Penaranda' finds 'Peñaranda'."""
    surname = fold(full_name).split()[-1]
    return re.search(rf"\b{re.escape(surname)}\b", fold(text)) is not None


def mentions_any_name(text: str, full_names: Iterable[str]) -> bool:
    return any(mentions_name(text, name) for name in full_names)


def mentions_euros(text: str, amount: int) -> bool:
    """'135,000,000', '135000000', '135 million', '€135M' for an exact euro amount."""
    spelled = [f"{amount:,}", str(amount)]
    if amount % 1_000_000 == 0:
        millions = amount // 1_000_000
        spelled += [rf"{millions}(?:\.0+)?\s*(?:million|m\b)"]
    return any(re.search(rf"(?<![\w.]){form}", text, re.IGNORECASE) for form in spelled)


def name_positions(text: str, full_names: Iterable[str]) -> list[int]:
    """First position of each surname in the answer, -1 when absent."""
    folded = fold(text)
    positions = []
    for name in full_names:
        match = re.search(rf"\b{re.escape(fold(name).split()[-1])}\b", folded)
        positions.append(match.start() if match else -1)
    return positions


def invocations_of(turn: ObservedTurn, tool_name: str) -> list[ToolInvocation]:
    return [call for call in turn.tool_invocations if call.name == tool_name]


def argument_matches(value: object, accepted: Collection[str]) -> bool:
    """A string argument containing any accepted token (accent/case-insensitive)."""
    return isinstance(value, str) and any(fold(token) in fold(value) for token in accepted)


def assert_tool_called(turn: ObservedTurn, tool_name: str) -> None:
    assert invocations_of(turn, tool_name), f"{tool_name} was never called ({turn.tools_called})"


def assert_no_tool_called(turn: ObservedTurn) -> None:
    assert turn.tools_called == [], f"a tool was called unnecessarily: {turn.tools_called}"


def assert_argument_accepted(
    turn: ObservedTurn, tool_name: str, argument: str, accepted: Collection[str]
) -> None:
    """Some call to `tool_name` passed an `argument` containing one of the accepted tokens."""
    calls = invocations_of(turn, tool_name)
    assert calls, f"{tool_name} was never called ({turn.tools_called})"
    assert any(argument_matches(call.arguments.get(argument), accepted) for call in calls), (
        f"no {tool_name} call had {argument} matching {sorted(accepted)}: "
        f"{[call.arguments.get(argument) for call in calls]}"
    )


def assert_entities_requested(
    turn: ObservedTurn,
    tool_name: str,
    argument_names: Collection[str],
    entities: Collection[Collection[str]],
) -> None:
    """One call to `tool_name` named every entity (each a set of accepted aliases) in any
    of its `argument_names`, in any order: 'Valdoria vs KRS' equals 'KRS vs Valdoria'.
    """
    calls = invocations_of(turn, tool_name)
    assert calls, f"{tool_name} was never called ({turn.tools_called})"
    for call in calls:
        values = [call.arguments.get(name) for name in argument_names]
        if all(any(argument_matches(v, aliases) for v in values) for aliases in entities):
            return
    raise AssertionError(f"no {tool_name} call named every entity {entities}: {calls}")


def assert_mentions_numbers(turn: ObservedTurn, values: Iterable[int], what: str) -> None:
    for value in values:
        assert mentions_number(turn.answer, value), f"answer does not state {what} {value}"


def assert_mentions_names(turn: ObservedTurn, full_names: Iterable[str]) -> None:
    for name in full_names:
        assert mentions_name(turn.answer, name), f"answer never names {name}"


def assert_names_in_order(turn: ObservedTurn, full_names: list[str]) -> None:
    positions = name_positions(turn.answer, full_names)
    assert -1 not in positions, f"answer omits one of {full_names}"
    assert positions == sorted(positions), f"answer lists {full_names} out of order"


def assert_acknowledges_missing_data(turn: ObservedTurn) -> None:
    assert ACKNOWLEDGES_MISSING_DATA.search(turn.answer), "answer never admits missing data"


def assert_reports_not_found(turn: ObservedTurn) -> None:
    """A tool was consulted, nothing was found, and no stat was invented."""
    assert turn.tools_called, "model answered without consulting any tool"
    assert NOT_FOUND_PHRASES.search(turn.answer), "answer never says nothing was found"
    assert_no_invented_stats(turn)


def assert_no_tool_and_no_stats(turn: ObservedTurn) -> None:
    assert_no_tool_called(turn)
    assert_no_invented_stats(turn)


def assert_not_stating(turn: ObservedTurn, pattern: re.Pattern[str], what: str) -> None:
    found = pattern.search(turn.answer)
    assert not found, f"answer invents {what}: {found.group(0)!r}"


def plain_value(value: object) -> object:
    """Enum members compare as their raw value ('goals', not SortField.GOALS)."""
    return getattr(value, "value", value)


def assert_call_where(
    turn: ObservedTurn, tool_name: str, predicate: Callable[[dict], bool], description: str
) -> None:
    """Some call to `tool_name` has arguments satisfying `predicate`."""
    calls = invocations_of(turn, tool_name)
    assert calls, f"{tool_name} was never called ({turn.tools_called})"
    assert any(predicate(call.arguments) for call in calls), (
        f"no {tool_name} call {description}: {[call.arguments for call in calls]}"
    )


def has_filter(arguments: dict, field: str, accepted_values: Collection[str]) -> bool:
    """A `query_player_stats` filter on `field` whose value is one of the accepted tokens."""
    return any(
        plain_value(item["field"]) == field
        and argument_matches(str(item["value"]), accepted_values)
        for item in arguments.get("filters", [])
    )


def mentions_date(text: str, day: date) -> bool:
    """ISO ('2026-10-02'), 'October 2, 2026', '2nd of October 2026' or 'Oct 2'."""
    month, short_month = day.strftime("%B"), day.strftime("%b")
    ordinal = r"(?:st|nd|rd|th)?"
    patterns = [
        day.isoformat(),
        rf"(?:{month}|{short_month})\.?\s+0?{day.day}{ordinal}\b",
        rf"\b0?{day.day}{ordinal}\s+(?:of\s+)?(?:{month}|{short_month})\b",
    ]
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)
