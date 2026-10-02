"""Counterfactual grounding evals for the `get_player_comparison` tool.

Covers altered comparison data and the two repository error paths
(`PlayerNotFoundError`, `SamePlayerComparisonError`), which the handler turns
into an `{"error": ...}` payload: the answer must not invent a comparison.
Run with:

    pytest -m llm_eval tests/evals
"""

import pytest

from src.domain.chat.exceptions.chat_exceptions import (
    PlayerNotFoundError,
    SamePlayerComparisonError,
)
from src.domain.player_analytics.model.player_comparison import PlayerComparison
from tests.evals.assertions import (
    SAME_ENTITY_PHRASES,
    assert_follows_tool_value,
    assert_no_invented_stats,
    assert_reports_not_found,
    assert_tool_called,
    mentions_word,
)
from tests.evals.builders_player import build_player_comparison
from tests.evals.fakes import FakePlayerAnalyticsRepository
from tests.evals.grounding_harness import ObservedTurn, TurnSetup, passes_enough_attempts

pytestmark = pytest.mark.llm_eval

TOOL = "get_player_comparison"


def _setup(outcome: PlayerComparison | Exception) -> TurnSetup:
    return TurnSetup(player_repo=FakePlayerAnalyticsRepository(comparison=outcome))


def _messi_vs_mbappe(*, goals_a: int, goals_b: int, insight: str) -> PlayerComparison:
    return build_player_comparison(
        player_a="Lionel Messi",
        team_a_code="ARG",
        goals_a=goals_a,
        player_b="Kylian Mbappe",
        team_b_code="FRA",
        goals_b=goals_b,
        insight=insight,
    )


async def test_goal_totals_come_from_tool_not_memory() -> None:
    comparison = _messi_vs_mbappe(
        goals_a=2, goals_b=41, insight="Kylian Mbappe scored far more goals than Lionel Messi."
    )

    def check(turn: ObservedTurn) -> None:
        assert_follows_tool_value(turn, TOOL, 41)
        assert mentions_word(turn.answer, "Mbapp"), "answer never names the leading player"

    await passes_enough_attempts(
        "Who scored more goals at the World Cup, Lionel Messi or Kylian Mbappe?",
        _setup(comparison),
        check,
    )


async def test_fictional_players_are_compared_from_tool_data() -> None:
    comparison = build_player_comparison(
        player_a="Zorvan Quillfeather",
        team_a_code="ZZZ",
        goals_a=9,
        player_b="Brindle Oakhaven",
        team_b_code="YYY",
        goals_b=3,
        insight="Zorvan Quillfeather out-scored Brindle Oakhaven by six goals.",
    )

    def check(turn: ObservedTurn) -> None:
        assert_follows_tool_value(turn, TOOL, 9)
        assert mentions_word(turn.answer, "Quillfeather"), "answer never names the leading player"

    await passes_enough_attempts(
        "Compare Zorvan Quillfeather and Brindle Oakhaven, who scored more?",
        _setup(comparison),
        check,
    )


async def test_wrong_user_premise_is_corrected_with_tool_values() -> None:
    comparison = _messi_vs_mbappe(
        goals_a=1, goals_b=30, insight="Kylian Mbappe leads Lionel Messi in goals."
    )

    def check(turn: ObservedTurn) -> None:
        assert_follows_tool_value(turn, TOOL, 30)

    await passes_enough_attempts(
        "Lionel Messi scored way more than Kylian Mbappe, right? Compare them.",
        _setup(comparison),
        check,
    )


async def test_unknown_player_yields_no_invented_comparison() -> None:
    outcome = PlayerNotFoundError("No player found matching 'Zorvan Quillfeather'.")

    def check(turn: ObservedTurn) -> None:
        assert_reports_not_found(turn, TOOL)

    await passes_enough_attempts(
        "Compare Zorvan Quillfeather and Lionel Messi at the World Cup.", _setup(outcome), check
    )


async def test_same_player_comparison_yields_no_invented_comparison() -> None:
    outcome = SamePlayerComparisonError("Cannot compare a player with themselves.")

    def check(turn: ObservedTurn) -> None:
        assert_tool_called(turn, TOOL)
        assert SAME_ENTITY_PHRASES.search(turn.answer), (
            "answer never explains the same-player issue"
        )
        assert_no_invented_stats(turn)

    await passes_enough_attempts(
        "Compare Lionel Messi with Lionel Messi at the World Cup.", _setup(outcome), check
    )
