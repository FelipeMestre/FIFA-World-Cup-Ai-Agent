"""Layer B no-data cases for rankings, and chat turns that need no tool or that no tool answers.

Rankings: `query_player_stats` over filters that match nobody (a team without a roster, a
position nobody plays, an absurd threshold, a club window without rows). Honest means "nobody
matches / no data"; invented means a numbered ranking, a count the tool never returned, or a
player of the wrong team. Ostravia has two roster rows of zeros, so a total-goals ranking may
legitimately list both with 0 goals; a per-90 ranking is empty (no minutes).

Chat: a first message with an empty history (the harness always starts with none) that needs
no tool, and questions for data no tool provides (injury, salary, attendance).

Not repeated here (already in `test_llm_unanswerable.py`): greeting, capabilities, off-topic
recipe, tickets and weather, prediction.
"""

import re

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.evals.grounding_harness import ObservedTurn
from tests.golden import llm_facts as facts
from tests.golden.fixture_empty import OSTRAVIA
from tests.golden.llm_assertions import (
    assert_acknowledges_missing_data,
    assert_no_tool_and_no_stats,
    assert_not_stating,
)
from tests.golden.llm_cases import GoldenLlmCase, run_golden_case
from tests.golden.llm_no_data import (
    assert_no_money,
    honest_empty_check,
    players_outside,
)
from tests.golden.no_data_cases import UNKNOWN_TEAM

pytestmark = pytest.mark.llm_eval

_QUERY = "query_player_stats"
_KRS_ID = facts.team_by_code("KRS").team_id
_INJURY_DETAIL = re.compile(
    r"out for \d|\d+\s*(?:weeks?|months?|days?)|hamstring|ligament|fracture|sprain",
    re.IGNORECASE,
)
_PAY_FIGURE = re.compile(
    r"\d[\d,.]*\s*(?:k|m|million|thousand)?\s*(?:per|a|/)\s*(?:week|year|month)", re.I
)
_CROWD_FIGURE = re.compile(
    r"\d{2,3}[,.]?\d{3}|\d+\s*(?:fans|spectators|people|attendees|supporters)", re.IGNORECASE
)


def _ranking_check(foreign_names=(), **knobs):
    return honest_empty_check({_QUERY}, foreign_names=foreign_names, no_ranking=True, **knobs)


def _no_tool_and_no_money(turn: ObservedTurn) -> None:
    assert_no_tool_and_no_stats(turn)
    assert_no_money(turn)


def _data_not_provided(forbidden: re.Pattern[str], what: str):
    def check(turn: ObservedTurn) -> None:
        assert_acknowledges_missing_data(turn)
        assert_not_stating(turn, forbidden, what)

    return check


# Either an honest empty answer, or the two real roster rows of zeros; never a nonzero count.
_OSTRAVIA_ZEROS_OR_EMPTY = honest_empty_check(
    {_QUERY}, foreign_names=players_outside(OSTRAVIA.team_id)
)

RANKING_CASES = [
    GoldenLlmCase(
        "ranking-team-without-roster",
        "Who are Thalmoor's top scorers at the World Cup?",
        _ranking_check(players_outside()),
    ),
    GoldenLlmCase(
        "ranking-per-90-without-minutes",
        "Rank Ostravia's players by goals per 90 minutes.",
        _OSTRAVIA_ZEROS_OR_EMPTY,
    ),
    GoldenLlmCase(
        "ranking-total-goals-all-zero",
        "top scorer of ostravia at the world cup? how many goals did he score",
        _OSTRAVIA_ZEROS_OR_EMPTY,
    ),
    GoldenLlmCase(
        "ranking-goalkeeper-saves-unmeasured",
        "Which Ostravia goalkeeper has made the most saves?",
        _OSTRAVIA_ZEROS_OR_EMPTY,
    ),
    GoldenLlmCase(
        "ranking-position-nobody-plays",
        "Show me Karsovia's best defenders by minutes played.",
        _ranking_check(players_outside(_KRS_ID)),
    ),
    GoldenLlmCase(
        "ranking-absurd-threshold",
        "Which Valdoria players have scored at least 50 goals at the World Cup?",
        _ranking_check(players_outside(), allowed_counts={0, 50}),
    ),
    GoldenLlmCase(
        "ranking-club-window-without-linked-seasons",
        "Who scored the most Premier League goals for Ostravia in 2025?",
        _ranking_check(players_outside(OSTRAVIA.team_id), allowed_counts={0}),
    ),
    GoldenLlmCase(
        "ranking-club-window-before-any-data",
        "Top Champions League scorers from Valdoria in the 2019/20 season?",
        _ranking_check(players_outside(), allowed_counts={0}),
    ),
    GoldenLlmCase(
        "ranking-unknown-nationality",
        f"List the best players from {UNKNOWN_TEAM} by goals.",
        _ranking_check(players_outside()),
    ),
]

CHAT_CASES = [
    GoldenLlmCase(
        "chat-first-message-spanish-greeting", "Hola, buenas tardes!", _no_tool_and_no_money
    ),
    GoldenLlmCase("chat-first-message-thanks", "thanks a lot", _no_tool_and_no_money),
    GoldenLlmCase("chat-first-message-bare-punctuation", "???", _no_tool_and_no_money),
    GoldenLlmCase(
        "chat-first-message-follow-up-without-context",
        "And what about his goals?",
        _no_tool_and_no_money,
    ),
    GoldenLlmCase(
        "unanswerable-injury-status",
        "Is Dario Montefusco injured right now and how long will he be out?",
        _data_not_provided(_INJURY_DETAIL, "an injury detail"),
    ),
    GoldenLlmCase(
        "unanswerable-salary",
        "How much does Rafael Ortegon earn per week?",
        _data_not_provided(_PAY_FIGURE, "a salary"),
    ),
    GoldenLlmCase(
        "unanswerable-attendance",
        "How many fans attended the Valdoria vs Karsovia final?",
        _data_not_provided(_CROWD_FIGURE, "an attendance figure"),
    ),
]

CASES = RANKING_CASES + CHAT_CASES


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.case_id)
async def test_no_data_ranking_and_chat_golden_case(
    golden_session: AsyncSession, case: GoldenLlmCase
) -> None:
    await run_golden_case(golden_session, case)
