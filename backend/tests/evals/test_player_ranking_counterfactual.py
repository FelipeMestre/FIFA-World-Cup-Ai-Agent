"""Counterfactual grounding evals for the `query_player_stats` tool.

The ranking order and values differ from reality; an empty ranking must not
lead the model to name players from memory. Run with:

    pytest -m llm_eval tests/evals
"""

import pytest

from src.domain.player_analytics.model.player_ranking import PlayerRanking
from tests.evals.assertions import (
    assert_follows_tool_value,
    assert_reports_not_found,
    assert_tool_called,
    mentions_word,
)
from tests.evals.builders_player import build_goals_ranking, build_ranking_row
from tests.evals.fakes import FakePlayerAnalyticsRepository
from tests.evals.grounding_harness import ObservedTurn, TurnSetup, passes_enough_attempts

pytestmark = pytest.mark.llm_eval

TOOL = "query_player_stats"


def _setup(ranking: PlayerRanking | None) -> TurnSetup:
    return TurnSetup(player_repo=FakePlayerAnalyticsRepository(ranking=ranking))


def _name_positions(answer: str, names: list[str]) -> list[int]:
    return [answer.find(name) for name in names]


async def test_ranking_order_comes_from_tool_not_memory() -> None:
    names = ["Fenwick Plimsoll", "Zorvan Quillfeather", "Brindle Oakhaven"]
    ranking = build_goals_ranking(
        [
            build_ranking_row(rank=rank, name=name, team_code="ZZZ", goals=goals)
            for rank, (name, goals) in enumerate(zip(names, [14, 11, 9], strict=True), start=1)
        ]
    )

    def check(turn: ObservedTurn) -> None:
        assert_tool_called(turn, TOOL)
        positions = _name_positions(turn.answer, names)
        assert all(position >= 0 for position in positions), "answer omits a ranked player"
        assert positions == sorted(positions), "answer reorders the tool's ranking"

    await passes_enough_attempts(
        "Who are the top 3 goal scorers at the World Cup? List them in order.",
        _setup(ranking),
        check,
    )


async def test_top_scorer_value_comes_from_tool_not_memory() -> None:
    ranking = build_goals_ranking(
        [build_ranking_row(rank=1, name="Neymar", team_code="BRA", goals=21)]
    )

    def check(turn: ObservedTurn) -> None:
        assert_follows_tool_value(turn, TOOL, 21)
        assert mentions_word(turn.answer, "Neymar"), "answer never names the tool's top scorer"

    await passes_enough_attempts(
        "Who is the top scorer at the World Cup and how many goals did they score?",
        _setup(ranking),
        check,
    )


async def test_wrong_user_premise_is_corrected_with_tool_ranking() -> None:
    ranking = build_goals_ranking(
        [build_ranking_row(rank=1, name="Orlando Pemberton", team_code="ZZZ", goals=17)]
    )

    def check(turn: ObservedTurn) -> None:
        assert_follows_tool_value(turn, TOOL, 17)
        assert mentions_word(turn.answer, "Pemberton"), "answer never names the tool's top scorer"

    await passes_enough_attempts(
        "Lionel Messi is the top scorer of this World Cup, isn't he?", _setup(ranking), check
    )


async def test_empty_ranking_yields_no_invented_players() -> None:
    def check(turn: ObservedTurn) -> None:
        assert_reports_not_found(turn, TOOL)

    await passes_enough_attempts(
        "Which goalkeepers scored more than 10 goals at the World Cup?", _setup(None), check
    )
