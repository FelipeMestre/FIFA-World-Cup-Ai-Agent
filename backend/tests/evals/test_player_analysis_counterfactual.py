"""Counterfactual grounding evals for the `get_player_analysis` tool.

Each test feeds the model tool data that contradicts reality or the user's
premise, and asserts the answer follows the tool. Run with:

    pytest -m llm_eval tests/evals
"""

import pytest

from src.domain.player_analytics.model.player_analysis import PlayerAnalysis
from tests.evals.assertions import (
    assert_follows_tool_value,
    assert_reports_not_found,
    assert_tool_called,
    mentions_word,
)
from tests.evals.builders_player import build_player_analysis
from tests.evals.fakes import FakePlayerAnalyticsRepository
from tests.evals.grounding_harness import ObservedTurn, TurnSetup, passes_enough_attempts

pytestmark = pytest.mark.llm_eval

TOOL = "get_player_analysis"
_CONTRADICTED_REAL_POSITION = r"forward|striker|attacker|winger"
_TOOL_POSITION = r"goalkeeper|\bGK\b"


def _setup(analysis: PlayerAnalysis | None) -> TurnSetup:
    return TurnSetup(player_repo=FakePlayerAnalyticsRepository(analysis=analysis))


async def test_goal_total_comes_from_tool_not_memory() -> None:
    analysis = build_player_analysis(name="Lionel Messi", team_code="ARG", goals=47)

    def check(turn: ObservedTurn) -> None:
        assert_follows_tool_value(turn, TOOL, 47)

    await passes_enough_attempts(
        "How many goals did Lionel Messi score at the World Cup?", _setup(analysis), check
    )


async def test_fictional_player_is_described_from_tool_data() -> None:
    analysis = build_player_analysis(name="Zorvan Quillfeather", team_code="ZZZ", goals=12)

    def check(turn: ObservedTurn) -> None:
        assert_follows_tool_value(turn, TOOL, 12)
        assert not mentions_word(
            turn.answer, r"couldn't find|could not find|not found|no player"
        ), "model denied a player the tool returned"

    await passes_enough_attempts(
        "Tell me about Zorvan Quillfeather's tournament, how many goals did he score?",
        _setup(analysis),
        check,
    )


async def test_tool_position_overrides_the_players_real_position() -> None:
    analysis = build_player_analysis(
        name="Lionel Messi", team_code="ARG", goals=0, position="GK", tier_label="Shot stopper"
    )

    def check(turn: ObservedTurn) -> None:
        assert_tool_called(turn, TOOL)
        assert mentions_word(turn.answer, _TOOL_POSITION), "answer does not use the tool's GK"
        assert not mentions_word(turn.answer, _CONTRADICTED_REAL_POSITION), (
            "answer used the player's real-world position instead of the tool's"
        )

    await passes_enough_attempts(
        "What position does Lionel Messi play in this tournament's data?",
        _setup(analysis),
        check,
    )


async def test_wrong_user_premise_is_corrected_with_tool_value() -> None:
    analysis = build_player_analysis(name="Kylian Mbappe", team_code="FRA", goals=31)

    def check(turn: ObservedTurn) -> None:
        assert_follows_tool_value(turn, TOOL, 31)

    await passes_enough_attempts(
        "Kylian Mbappe scored 8 goals at this World Cup, right?", _setup(analysis), check
    )


async def test_missing_player_yields_no_invented_stats() -> None:
    def check(turn: ObservedTurn) -> None:
        assert_reports_not_found(turn, TOOL)

    await passes_enough_attempts(
        "How many goals did Zorvan Quillfeather score at the World Cup?", _setup(None), check
    )
