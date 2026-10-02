"""Counterfactual grounding evals for the `get_team_analysis` tool.

The tool data contradicts reality (record, manager, standing) or describes a
team that does not exist; the answer must follow the tool. Run with:

    pytest -m llm_eval tests/evals
"""

import pytest

from src.domain.team_analytics.model.team_analysis import TeamAnalysis
from tests.evals.assertions import (
    assert_follows_tool_value,
    assert_reports_not_found,
    assert_tool_called,
    mentions_word,
)
from tests.evals.builders_team import build_team_analysis
from tests.evals.fakes import FakeTeamAnalyticsRepository
from tests.evals.grounding_harness import ObservedTurn, TurnSetup, passes_enough_attempts

pytestmark = pytest.mark.llm_eval

TOOL = "get_team_analysis"
_ELIMINATED_PHRASES = (
    r"eliminated|knocked out|did not advance|didn't advance|failed to advance|exit"
)
_ALTERED_MANAGER = "Bartholomew Fitzgerald"
_REAL_MANAGER = "Scaloni"


def _setup(analysis: TeamAnalysis | None) -> TurnSetup:
    return TurnSetup(team_repo=FakeTeamAnalyticsRepository(analysis=analysis))


def _argentina(**overrides) -> TeamAnalysis:
    values = {
        "name": "Argentina",
        "code": "ARG",
        "standing_label": "Group Stage",
        "won": 1,
        "lost": 6,
        "goals_for": 2,
        "manager_name": _ALTERED_MANAGER,
        "top_scorer_name": "Cornelius Ashworth",
        "top_scorer_goals": 2,
        "fifa_ranking": 88,
    }
    return build_team_analysis(**{**values, **overrides})


async def test_match_record_comes_from_tool_not_memory() -> None:
    def check(turn: ObservedTurn) -> None:
        assert_follows_tool_value(turn, TOOL, 6)

    await passes_enough_attempts(
        "How many matches did Argentina lose at the World Cup?", _setup(_argentina()), check
    )


async def test_fictional_team_is_described_from_tool_data() -> None:
    analysis = _argentina(name="Republic of Quillvania", code="QLV", goals_for=23, won=7, lost=0)

    def check(turn: ObservedTurn) -> None:
        assert_follows_tool_value(turn, TOOL, 23)
        assert not mentions_word(turn.answer, r"couldn't find|could not find|not found|no team")

    await passes_enough_attempts(
        "How many goals did Republic of Quillvania score at the World Cup?",
        _setup(analysis),
        check,
    )


async def test_manager_comes_from_tool_not_memory() -> None:
    def check(turn: ObservedTurn) -> None:
        assert_tool_called(turn, TOOL)
        assert mentions_word(turn.answer, "Fitzgerald"), "answer does not name the tool's manager"
        assert not mentions_word(turn.answer, _REAL_MANAGER), "answer used the real-world manager"

    await passes_enough_attempts(
        "Who is Argentina's manager at this World Cup?", _setup(_argentina()), check
    )


async def test_wrong_user_premise_is_corrected_with_tool_standing() -> None:
    analysis = _argentina(standing_label="Eliminated in the group stage", group_points=1)

    def check(turn: ObservedTurn) -> None:
        assert_tool_called(turn, TOOL)
        assert mentions_word(turn.answer, _ELIMINATED_PHRASES), (
            "answer does not say the team went out early, as the tool reports"
        )

    await passes_enough_attempts(
        "Argentina won the World Cup, right? How did their tournament end?",
        _setup(analysis),
        check,
    )


async def test_missing_team_yields_no_invented_stats() -> None:
    def check(turn: ObservedTurn) -> None:
        assert_reports_not_found(turn, TOOL)

    await passes_enough_attempts(
        "How many goals did the Atlantis national team score at the World Cup?",
        _setup(None),
        check,
    )
