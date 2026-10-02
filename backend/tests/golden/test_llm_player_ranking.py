"""Layer B golden cases for `query_player_stats` ranking questions.

Questions always scope to one fixture team ("Valdoria's ...") so the model's nationality
filter keeps the ranking inside fixture rows; the shared dev database also holds the real
dataset. Order is asserted with first-mention positions of surnames, so the answer may
format the ranking as a list, a table or prose.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.evals.grounding_harness import ObservedTurn
from tests.golden import expected, fixture_data
from tests.golden import llm_facts as facts
from tests.golden.llm_assertions import (
    assert_call_where,
    assert_mentions_numbers,
    assert_names_in_order,
    assert_tool_called,
    has_filter,
    mentions_name,
    mentions_number,
    plain_value,
)
from tests.golden.llm_cases import GoldenLlmCase, run_golden_case

pytestmark = pytest.mark.llm_eval

_QUERY = "query_player_stats"
_VLD_TOKENS = facts.team_aliases(facts.team_by_code("VLD"))
_KRS_TOKENS = facts.team_aliases(facts.team_by_code("KRS"))
_ORTEGON = facts.stat(fixture_data.ORTEGON_ID)
_MONTEFUSCO = facts.stat(fixture_data.MONTEFUSCO_ID)
_KOZHUKAR = facts.stat(fixture_data.KOZHUKAR_ID)


def _top_two_scorers(turn: ObservedTurn) -> None:
    assert_call_where(
        turn,
        _QUERY,
        lambda args: (
            plain_value(args["sort_by"]) == "goals" and has_filter(args, "nationality", _VLD_TOKENS)
        ),
        "sorted by goals and restricted to Valdoria",
    )
    assert_names_in_order(turn, expected.VALDORIA_BY_GOALS[:2])
    assert_mentions_numbers(turn, [_ORTEGON.goals, _MONTEFUSCO.goals], "the goals")


def _forwards_by_goals(turn: ObservedTurn) -> None:
    assert_tool_called(turn, _QUERY)
    assert_names_in_order(turn, expected.VALDORIA_FORWARDS_BY_GOALS)


def _goal_contributions(turn: ObservedTurn) -> None:
    assert_tool_called(turn, _QUERY)
    assert_names_in_order(turn, expected.VALDORIA_BY_GOALS[:2])
    contributions = [s.goals + s.assists for s in (_ORTEGON, _MONTEFUSCO)]
    assert_mentions_numbers(turn, contributions, "the goal contributions")


def _karsovia_goalkeeper_saves(turn: ObservedTurn) -> None:
    assert_tool_called(turn, _QUERY)
    assert mentions_name(turn.answer, "Pavel Kozhukar"), "answer never names Karsovia's goalkeeper"
    assert mentions_number(turn.answer, _KOZHUKAR.saves)


CASES = [
    GoldenLlmCase(
        "ranking-top-two-scorers",
        "Who are Valdoria's two top scorers at the World Cup? List them in order with their goals.",
        _top_two_scorers,
    ),
    GoldenLlmCase(
        "ranking-forwards-by-goals",
        "Among Valdoria's forwards, who has scored the most? Rank them for me.",
        _forwards_by_goals,
    ),
    GoldenLlmCase(
        "ranking-goal-contributions",
        "Rank the best two Valdoria players by goals plus assists in this tournament.",
        _goal_contributions,
    ),
    GoldenLlmCase(
        "ranking-goalkeeper-saves",
        "Which Karsovia goalkeeper has made the most saves at the World Cup, and how many?",
        _karsovia_goalkeeper_saves,
    ),
]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.case_id)
async def test_player_ranking_golden_case(
    golden_session: AsyncSession, case: GoldenLlmCase
) -> None:
    await run_golden_case(golden_session, case)
