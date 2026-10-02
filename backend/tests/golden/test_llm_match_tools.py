"""Layer B golden cases for `get_match_analysis`, including repeat fixtures and the chip.

Valdoria and Karsovia met twice (group stage 2-1, final 1-1 and 4-3 on penalties for
Karsovia). When the stage is named the tool resolves one match; when it is not, the tool
returns a candidate list and the safe answer names both matches. The pinned-chip cases
prepend the production directive (`ChatService._build_match_directive`) as a second
system message, then ask a vague follow-up.

The repository does not resolve accent-less team names, so the "Servenia" case accepts the
correct score (model retried with the accent or the code) or an honest not-found.
"""

import re

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.evals.assertions import NOT_FOUND_PHRASES, assert_no_invented_stats, mentions_word
from tests.evals.grounding_harness import ObservedTurn
from tests.golden import fixture_data, fixture_matches
from tests.golden import llm_facts as facts
from tests.golden.llm_assertions import (
    argument_matches,
    assert_call_where,
    assert_entities_requested,
    assert_mentions_names,
    assert_tool_called,
    mentions_name,
    mentions_score,
)
from tests.golden.llm_cases import GoldenLlmCase, run_golden_case

pytestmark = pytest.mark.llm_eval

_TOOL = "get_match_analysis"
_SIDES = ("home_team_name", "away_team_name")
_GROUP = facts.match(fixture_matches.GROUP_VLD_KRS_ID)
_FINAL = facts.match(fixture_matches.FINAL_KRS_VLD_ID)
_SRV_MATCH = facts.match(fixture_matches.GROUP_SRV_VLD_ID)
_VLD = facts.team_aliases(facts.team_by_code("VLD"))
_KRS = facts.team_aliases(facts.team_by_code("KRS"))
_SRV = facts.team_aliases(facts.team_by_code("SRV")) | {"Servenia"}
_ORTEGON = facts.player(fixture_data.ORTEGON_ID).player_name
_MONTEFUSCO = facts.player(fixture_data.MONTEFUSCO_ID).player_name
_RAVELLI_KRS = facts.player(fixture_data.RAVELLI_KRS_ID).player_name
_KOZHUKAR = facts.player(fixture_data.KOZHUKAR_ID).player_name
_VALDORIA_WON_FINAL = re.compile(
    r"Valdoria (?:won|beat|defeated) (?:Karsovia )?(?:in the final|the final|on penalties)",
    re.IGNORECASE,
)


def _selects(stage_token: str, match: fixture_matches.MatchSeed):
    """Arguments that single out `match` among the two Valdoria-Karsovia fixtures."""

    def predicate(arguments: dict) -> bool:
        return argument_matches(arguments.get("stage"), {stage_token}) or (
            arguments.get("date") == match.match_date.isoformat()
        )

    return predicate


def _assert_final_ended_level_and_on_penalties(turn: ObservedTurn) -> None:
    assert mentions_score(turn.answer, _FINAL.home_score, _FINAL.away_score)
    assert mentions_word(turn.answer, r"penalt|shoot-?out"), "answer never mentions the shootout"
    assert mentions_score(turn.answer, _FINAL.home_penalty_score, _FINAL.away_penalty_score)


def _valdoria_servenia_score_and_scorers(turn: ObservedTurn) -> None:
    assert_entities_requested(turn, _TOOL, _SIDES, [_VLD, _SRV])
    assert mentions_score(turn.answer, _SRV_MATCH.home_score, _SRV_MATCH.away_score)
    assert_mentions_names(turn, [_ORTEGON, _MONTEFUSCO])


def _servenia_score_or_honest_not_found(turn: ObservedTurn) -> None:
    assert_tool_called(turn, _TOOL)
    if NOT_FOUND_PHRASES.search(turn.answer):
        assert_no_invented_stats(turn)
        return
    assert mentions_score(turn.answer, _SRV_MATCH.home_score, _SRV_MATCH.away_score)


def _final_by_stage(turn: ObservedTurn) -> None:
    assert_entities_requested(turn, _TOOL, _SIDES, [_VLD, _KRS])
    assert_call_where(turn, _TOOL, _selects("final", _FINAL), "singled out the final")
    _assert_final_ended_level_and_on_penalties(turn)
    assert mentions_name(turn.answer, "Karsovia")
    assert not _VALDORIA_WON_FINAL.search(turn.answer), "answer says Valdoria won the final"


def _group_game_by_stage(turn: ObservedTurn) -> None:
    assert_call_where(turn, _TOOL, _selects("group", _GROUP), "singled out the group game")
    assert mentions_score(turn.answer, _GROUP.home_score, _GROUP.away_score)
    assert_mentions_names(turn, [_ORTEGON])


def _teams_met_twice_names_both_matches(turn: ObservedTurn) -> None:
    assert_entities_requested(turn, _TOOL, _SIDES, [_VLD, _KRS])
    assert mentions_word(turn.answer, r"\bgroup\b"), "answer never mentions the group-stage game"
    assert mentions_word(turn.answer, r"\bfinal\b"), "answer never mentions the final"


def _final_player_of_the_match(turn: ObservedTurn) -> None:
    assert_call_where(turn, _TOOL, _selects("final", _FINAL), "singled out the final")
    assert_mentions_names(turn, [_KOZHUKAR])


def _pinned_final_ending(turn: ObservedTurn) -> None:
    assert_call_where(turn, _TOOL, _selects("final", _FINAL), "singled out the pinned final")
    _assert_final_ended_level_and_on_penalties(turn)


def _pinned_group_scorers(turn: ObservedTurn) -> None:
    assert_call_where(turn, _TOOL, _selects("group", _GROUP), "singled out the pinned group game")
    assert_mentions_names(turn, [_ORTEGON, _RAVELLI_KRS])


def _pinned_group_best_player(turn: ObservedTurn) -> None:
    assert_call_where(turn, _TOOL, _selects("group", _GROUP), "singled out the pinned group game")
    assert_mentions_names(turn, [_ORTEGON])


CASES = [
    GoldenLlmCase(
        "match-single-match-score-and-scorers",
        "What was the score when Valdoria played Sérvenia, and who scored?",
        _valdoria_servenia_score_and_scorers,
    ),
    GoldenLlmCase(
        "match-single-match-accentless-team",
        "What was the score of Valdoria against Servenia?",
        _servenia_score_or_honest_not_found,
    ),
    GoldenLlmCase(
        "match-repeat-fixture-final-by-stage",
        "How did the final between Valdoria and Karsovia end? Who won?",
        _final_by_stage,
    ),
    GoldenLlmCase(
        "match-repeat-fixture-group-by-stage",
        "What was the result of the group stage game between Valdoria and Karsovia?",
        _group_game_by_stage,
    ),
    GoldenLlmCase(
        "match-repeat-fixture-unspecified-names-both",
        "How did the Valdoria vs Karsovia match go?",
        _teams_met_twice_names_both_matches,
    ),
    GoldenLlmCase(
        "match-repeat-fixture-player-of-the-match",
        "Who was man of the match in the Karsovia-Valdoria final?",
        _final_player_of_the_match,
    ),
    GoldenLlmCase(
        "match-pinned-final-how-did-it-end",
        "How did it end?",
        _pinned_final_ending,
        pinned_match_id=_FINAL.match_id,
    ),
    GoldenLlmCase(
        "match-pinned-group-who-scored",
        "Who scored in this game?",
        _pinned_group_scorers,
        pinned_match_id=_GROUP.match_id,
    ),
    GoldenLlmCase(
        "match-pinned-group-best-player",
        "who was the best player?",
        _pinned_group_best_player,
        pinned_match_id=_GROUP.match_id,
    ),
]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.case_id)
async def test_match_golden_case(golden_session: AsyncSession, case: GoldenLlmCase) -> None:
    await run_golden_case(golden_session, case)
