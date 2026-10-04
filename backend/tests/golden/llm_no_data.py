"""Shared checks for the Layer B no-data cases (real LLM over the empty fixture entities).

Each no-data case must pass the same three tests: the right tool was consulted, the answer
says the data is missing / zero / not found / not played, and the answer invents nothing.
`honest_empty_check` builds that check from a few knobs; the lower-level assertions are
exposed for the cases that need something more specific (a scheduled match, a career).

"Invents nothing" is checked only through unmistakable shapes, so a phrasing change never
fails an honest answer: a count next to a football unit that is not an allowed value, a
score, a euro amount, a numbered ranking, a club the player was never linked to, or a
fixture player who does not belong to the entity asked about.
"""

import re
from collections.abc import Callable, Collection, Iterable

from tests.evals.grounding_harness import ObservedTurn
from tests.golden import fixture_empty, llm_facts
from tests.golden.fixture_data import PLAYERS
from tests.golden.llm_assertions import (
    assert_argument_accepted,
    mentions_any_name,
    number_forms,
)

ZERO_ONLY = frozenset({0})

NO_DATA_PHRASES = re.compile(
    r"\bno (?:matches|games|goals|stats|statistics|players|squad|roster|career|club|clubs|"
    r"transfers?|seasons?|results?|data|records?|information|appearances|minutes|fixtures?|"
    r"one|player|team|match|rankings?)\b|"
    r"not (?:yet )?(?:played|recorded|measured|available|provided|listed|found|scored)|"
    r"(?:hasn't|has not|haven't|have not|didn't|did not|never) (?:yet )?"
    r"(?:played|play|scored|met|meet|qualified|made|appeared|featured|taken|faced|face)|"
    r"\bzero\b|(?<![\d\-–:.])0\s+(?:goals?|matches|games|minutes|apps|appearances|saves?|points|"
    r"clean sheets?|cards|assists?|wins|seasons?|transfers?)|"
    r"\bno (?:\w+ ){1,3}(?:matched|found|available|recorded|listed|measured)|"
    r"\bnone\b|nobody|without|yet to|couldn't|could not|unable|don't have|do not have|"
    r"unavailable|\bempty\b|\bnothing\b|cannot|can't|doesn't|does not",
    re.IGNORECASE,
)
SCHEDULED_PHRASES = re.compile(
    r"scheduled|not (?:yet )?(?:been )?played|(?:hasn't|has not|haven't|have not) "
    r"(?:yet )?(?:been )?(?:played|started|taken place|kicked off)|yet to (?:be )?(?:play|played)|"
    r"upcoming|no result|not (?:yet )?started|to be played|will be played|will take place|"
    r"pending|placeholder|no final score|no score",
    re.IGNORECASE,
)
_PLAYED_RESULT_CLAIM = re.compile(r"\b(?:won|beat|defeated|victory|drew)\b", re.IGNORECASE)

_STAT_UNITS = (
    r"goals?|assists?|matches|games|wins|losses|draws|points|appearances|apps|minutes|"
    r"cards|clean sheets?|saves?|shots?|transfers?|seasons?|clubs?|caps|conceded"
)
_WORD_TO_NUMBER = {number_forms(value)[1]: value for value in range(21)}
_COUNT_BEFORE_UNIT = re.compile(
    rf"(?<![\w.,])(\d+(?:[.,]\d+)*|{'|'.join(_WORD_TO_NUMBER)})\s+(?:{_STAT_UNITS})\b",
    re.IGNORECASE,
)
_COUNT_AFTER_UNIT = re.compile(rf"\b(?:{_STAT_UNITS})\s*[:=]\s*(\d+(?:\.\d+)?)", re.IGNORECASE)
_SCORE = re.compile(r"(?<![\w.\-])(\d{1,2})\s*[-–:]\s*(\d{1,2})(?![\w\-])")
_MONEY = re.compile(r"[€$£]\s?\d|\d\s*(?:million|m\b|k\b|euros?|eur\b|usd|dollars)", re.IGNORECASE)
_NUMBERED_RANKING = re.compile(r"(?m)^\s*(?:#\s?)?1\s*[.):]\s+\S")
_CLUB_CLAIM = re.compile(
    r"\b(?:plays?|played|playing|signed|joined|joins|moved|transferred|career at|"
    r"currently at|currently with|currently for)\s+(?:for|with|to|from|at)?\s*"
    r"((?:[A-Z][\w'.-]*)(?:\s+[A-Z][\w'.-]*){0,3})"
)
_SCHEDULED_ALIASES = {
    name
    for team in (fixture_empty.VARNHOLM, fixture_empty.QUELLIS)
    for name in llm_facts.team_aliases(team)
}
_WORLD_CUP_WORDS = frozenset({"The", "A", "An", "World", "FIFA", "Football"})


def claimed_counts(text: str) -> list[float]:
    """Every football count the answer states: a number next to a unit ('3 goals', 'saves: 5')."""
    values = []
    for raw in [m.group(1) for m in _COUNT_BEFORE_UNIT.finditer(text)] + [
        m.group(1) for m in _COUNT_AFTER_UNIT.finditer(text)
    ]:
        word = raw.lower()
        is_word = word in _WORD_TO_NUMBER
        values.append(float(_WORD_TO_NUMBER[word] if is_word else raw.replace(",", "")))
    return values


def assert_counts_within(turn: ObservedTurn, allowed: Collection[float]) -> None:
    stated = claimed_counts(turn.answer)
    invented = [value for value in stated if value not in allowed]
    assert not invented, f"answer states counts the tools never returned: {invented}"


def assert_conveys_no_data(turn: ObservedTurn) -> None:
    assert NO_DATA_PHRASES.search(turn.answer), "answer never says the data is missing or zero"


def assert_no_scores(turn: ObservedTurn, allowed: Collection[tuple[int, int]] = ()) -> None:
    scores = [(int(a), int(b)) for a, b in _SCORE.findall(turn.answer)]
    invented = [score for score in scores if score not in allowed and score[::-1] not in allowed]
    assert not invented, f"answer states a score that was never played: {invented}"


def assert_no_money(turn: ObservedTurn) -> None:
    found = _MONEY.search(turn.answer)
    assert not found, f"answer states an amount of money: {found.group(0)!r}"


def assert_no_numbered_ranking(turn: ObservedTurn) -> None:
    assert not _NUMBERED_RANKING.search(turn.answer), "answer fabricates a numbered ranking"


def assert_names_absent(turn: ObservedTurn, full_names: Iterable[str]) -> None:
    named = mentions_any_name(turn.answer, full_names)
    assert not named, "answer names a player who does not belong to the entity asked about"


def assert_no_invented_club(turn: ObservedTurn, allowed_names: Collection[str]) -> None:
    """No 'plays for / signed with / joined X' where X is not a club the fixture links."""
    allowed = {name.casefold() for name in allowed_names}
    for match in _CLUB_CLAIM.finditer(turn.answer):
        words = [w for w in match.group(1).split() if w not in _WORLD_CUP_WORDS]
        club = " ".join(words)
        if club and not any(club.casefold().startswith(name) for name in allowed):
            raise AssertionError(f"answer invents a club: {club!r}")


def players_outside(*team_ids: int) -> list[str]:
    """Fixture players not on any of the given teams (all of them when none is given)."""
    return [
        seed.player_name
        for seed in (*PLAYERS, *fixture_empty.EMPTY_PLAYERS)
        if seed.team_id not in team_ids
    ]


def team_names_and_clubs(*team_names: str) -> set[str]:
    """Names an honest career answer may mention: the national team and the roster club."""
    return {*team_names, *{seed.club_team for seed in fixture_empty.EMPTY_PLAYERS}}


def honest_empty_check(
    tools: Collection[str],
    *,
    allowed_counts: Collection[float] = ZERO_ONLY,
    foreign_names: Iterable[str] = (),
    argument: tuple[str, str, Collection[str]] | None = None,
    allowed_scores: Collection[tuple[int, int]] | None = None,
    no_ranking: bool = False,
    no_money: bool = False,
    allowed_clubs: Collection[str] | None = None,
) -> Callable[[ObservedTurn], None]:
    """The common no-data check; each knob adds one 'invents nothing' assertion.

    `allowed_scores=()` forbids every score; `None` skips the score check.
    """
    foreign = list(foreign_names)

    def check(turn: ObservedTurn) -> None:
        assert set(tools) & set(turn.tools_called), f"none of {sorted(tools)} was called"
        if argument is not None:
            assert_argument_accepted(turn, *argument)
        assert_conveys_no_data(turn)
        assert_counts_within(turn, allowed_counts)
        if foreign:
            assert_names_absent(turn, foreign)
        if allowed_scores is not None:
            assert_no_scores(turn, allowed_scores)
        if no_ranking:
            assert_no_numbered_ranking(turn)
        if no_money:
            assert_no_money(turn)
        if allowed_clubs is not None:
            assert_no_invented_club(turn, allowed_clubs)

    return check


def scheduled_not_played_check(turn: ObservedTurn) -> None:
    """A scheduled match was asked about as if played: say 'scheduled / no result yet'.

    The tool itself answers with status Scheduled and a 0-0 placeholder (finding F5), so the
    placeholder may be mentioned as such, but no other score, winner or scorer may appear.
    """
    assert_argument_accepted(turn, "get_match_analysis", "home_team_name", _SCHEDULED_ALIASES)
    assert SCHEDULED_PHRASES.search(turn.answer), "answer never says the match is not played"
    assert_no_scores(turn, allowed={(0, 0)})
    assert not _PLAYED_RESULT_CLAIM.search(turn.answer), "answer presents a played result"
    assert_counts_within(turn, ZERO_ONLY)
    assert_names_absent(turn, players_outside(fixture_empty.VARNHOLM.team_id))
