"""Layer B golden cases for the team tools, through the real LLM and real repositories.

Covers `get_team_analysis` and `get_team_comparison`, name resolution by code and by
accent-less spelling. The repository does not resolve accent-less team names ("Servenia"
is not found, "Sérvenia" is), so that case accepts either the correct record (the model
retried with the accented spelling or the code) or an honest not-found, never a made-up
record.
"""

import re

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.evals.assertions import NOT_FOUND_PHRASES, assert_no_invented_stats, mentions_word
from tests.evals.grounding_harness import ObservedTurn
from tests.golden import expected
from tests.golden import llm_facts as facts
from tests.golden.llm_assertions import (
    assert_argument_accepted,
    assert_entities_requested,
    assert_mentions_names,
    assert_mentions_numbers,
    assert_tool_called,
    mentions_euros,
    mentions_name,
    mentions_number,
    mentions_score,
)
from tests.golden.llm_cases import GoldenLlmCase, run_golden_case

pytestmark = pytest.mark.llm_eval

_VLD = facts.team_by_code("VLD")
_KRS = facts.team_by_code("KRS")
_SRV = facts.team_by_code("SRV")
_ANALYSIS = "get_team_analysis"
_COMPARISON = "get_team_comparison"
_TEAM_COMPARISON_ARGS = ("team_a_name", "team_b_name")
_SHOOTOUT_LOSS_OUTCOME = re.compile(
    r"penalt|shoot-?out|lost|loss|defeat|beaten|eliminated|runner|second|came up short",
    re.IGNORECASE,
)


def _valdoria_goals_and_top_scorer(turn: ObservedTurn) -> None:
    assert_argument_accepted(turn, _ANALYSIS, "team_name", facts.team_aliases(_VLD))
    record = expected.VALDORIA_RECORD
    assert_mentions_numbers(turn, [record["goals_for"], record["goals_against"]], "goals")
    assert_mentions_names(turn, [expected.VALDORIA_TOP_SCORER])


def _karsovia_record_and_coach(turn: ObservedTurn) -> None:
    assert_argument_accepted(turn, _ANALYSIS, "team_name", facts.team_aliases(_KRS))
    record = expected.KARSOVIA_RECORD
    assert_mentions_numbers(turn, [record["goals_for"], record["goals_against"]], "goals")
    assert_mentions_names(turn, [_KRS.manager_name])


def _valdoria_tournament_exit(turn: ObservedTurn) -> None:
    assert_argument_accepted(turn, _ANALYSIS, "team_name", facts.team_aliases(_VLD))
    assert mentions_word(turn.answer, r"\bfinal\b"), "answer never says the run ended in the final"
    assert mentions_name(turn.answer, _KRS.team_name), "answer never names the final's opponent"
    assert _SHOOTOUT_LOSS_OUTCOME.search(turn.answer), "answer never says Valdoria did not win"


def _servenia_record_or_honest_not_found(turn: ObservedTurn) -> None:
    assert_tool_called(turn, _ANALYSIS)
    if NOT_FOUND_PHRASES.search(turn.answer):
        assert_no_invented_stats(turn)
        return
    assert mentions_name(turn.answer, _SRV.team_name), "answer is about some other team"
    assert mentions_number(turn.answer, expected.SERVENIA_RECORD["goals_against"])


def _valdoria_karsovia_head_to_head(turn: ObservedTurn) -> None:
    assert_entities_requested(
        turn,
        _COMPARISON,
        _TEAM_COMPARISON_ARGS,
        [facts.team_aliases(_VLD), facts.team_aliases(_KRS)],
    )
    assert mentions_euros(turn.answer, expected.VALDORIA_SQUAD_MARKET_VALUE)
    assert mentions_euros(turn.answer, expected.KARSOVIA_SQUAD_MARKET_VALUE)
    for _stage, a_score, b_score, _result, _penalties in expected.VLD_KRS_MEETINGS:
        assert mentions_score(turn.answer, a_score, b_score), f"missing {a_score}-{b_score}"


def _pre_tournament_ranking_by_codes(turn: ObservedTurn) -> None:
    assert_entities_requested(
        turn,
        _COMPARISON,
        _TEAM_COMPARISON_ARGS,
        [facts.team_aliases(_VLD), facts.team_aliases(_KRS)],
    )
    assert_mentions_numbers(
        turn, [_VLD.fifa_ranking_pre_tournament, _KRS.fifa_ranking_pre_tournament], "ranking"
    )


CASES = [
    GoldenLlmCase(
        "team-analysis-goals-and-top-scorer",
        "How did Valdoria do at the World Cup? I want the goals they scored and conceded, "
        "and who their top scorer is.",
        _valdoria_goals_and_top_scorer,
    ),
    GoldenLlmCase(
        "team-analysis-code-lowercase-and-coach",
        "whats krs record in the cup? and who is their coach",
        _karsovia_record_and_coach,
    ),
    GoldenLlmCase(
        "team-analysis-shootout-exit",
        "Did Valdoria win the World Cup? What happened in their last game?",
        _valdoria_tournament_exit,
    ),
    GoldenLlmCase(
        "team-analysis-accentless-name",
        "How did Servenia do in the tournament?",
        _servenia_record_or_honest_not_found,
    ),
    GoldenLlmCase(
        "team-comparison-squad-value-and-meetings",
        "Compare Valdoria and Karsovia: which squad is worth more, and how did their "
        "matches against each other go?",
        _valdoria_karsovia_head_to_head,
    ),
    GoldenLlmCase(
        "team-comparison-by-codes-ranking",
        "VLD vs KRS: who had the higher FIFA ranking before the tournament?",
        _pre_tournament_ranking_by_codes,
    ),
]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.case_id)
async def test_team_golden_case(golden_session: AsyncSession, case: GoldenLlmCase) -> None:
    await run_golden_case(golden_session, case)
