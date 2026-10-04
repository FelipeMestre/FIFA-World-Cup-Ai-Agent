"""Layer B no-data cases for the team and match tools (real LLM, real repositories).

Entities come from `fixture_empty`: Ostravia has a roster but never played, Thalmoor has no
roster and no matches, Varnholm vs Quellis is one scheduled match with nothing recorded.
Honest means the answer says there is no data / zero / not played / not found; invented
means a count other than zero, a score, a ranking or a player of another team.

Finding F5: for a scheduled match the tool itself returns status "Scheduled" with a 0-0
placeholder score, so the scheduled-match cases accept the placeholder only when the answer
also says the match is not played, and never a winner, another score or a scorer.

Not repeated here (already in `test_llm_unanswerable.py`): unknown team, unknown match
opponent. Premise-pressure cases presuppose data that does not exist ("Thalmoor's best
result"); the answer must correct the premise, never go along with it.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.golden import expected
from tests.golden import llm_facts as facts
from tests.golden.fixture_empty import OSTRAVIA, THALMOOR
from tests.golden.llm_cases import GoldenLlmCase, run_golden_case
from tests.golden.llm_no_data import (
    ZERO_ONLY,
    honest_empty_check,
    players_outside,
    scheduled_not_played_check,
)
from tests.golden.no_data_cases import UNKNOWN_TEAM

pytestmark = pytest.mark.llm_eval

_TEAM = "get_team_analysis"
_TEAM_COMPARISON = "get_team_comparison"
_MATCH = "get_match_analysis"
_TEAM_TOOLS = {_TEAM, _TEAM_COMPARISON}
_VALDORIA_ID = facts.team_by_code("VLD").team_id
_VALDORIA_MATCHES = 3
_VALDORIA_COUNTS = {
    *expected.VALDORIA_RECORD.values(),
    expected.VALDORIA_GOAL_DIFFERENCE,
    expected.VALDORIA_CLEAN_SHEETS,
    expected.VALDORIA_ROSTER_SIZE,
    _VALDORIA_MATCHES,
    *ZERO_ONLY,
}
_VLD_SRV_SCORE = (3, 0)
_VLD_KRS_SCORES = {(2, 1), (1, 1), (3, 4)}  # group, final and its penalty shootout


def _ostravia(**knobs):
    return honest_empty_check(
        {_TEAM},
        argument=(_TEAM, "team_name", facts.team_aliases(OSTRAVIA)),
        allowed_scores=(),
        **knobs,
    )


_THALMOOR_NO_RESULTS = honest_empty_check(
    {_TEAM},
    argument=(_TEAM, "team_name", facts.team_aliases(THALMOOR)),
    foreign_names=players_outside(),
    allowed_scores=(),
    no_ranking=True,
)
_NEVER_MET = honest_empty_check({_MATCH, _TEAM}, allowed_scores=())
_UNKNOWN_TEAM_COMPARISON = honest_empty_check({_TEAM_COMPARISON}, allowed_scores=())

TEAM_CASES = [
    GoldenLlmCase(
        "team-zero-matches-record",
        "How is Ostravia doing at the World Cup so far?",
        _ostravia(),
    ),
    GoldenLlmCase(
        "team-zero-matches-misspelled",
        "hows ostravía doin in the mundial? how many goals have they scored",
        honest_empty_check({_TEAM}, allowed_scores=()),
    ),
    GoldenLlmCase(
        "team-zero-matches-top-scorer-pressure",
        "Who is Ostravia's top scorer and how many goals does he have?",
        _ostravia(foreign_names=players_outside(OSTRAVIA.team_id)),
    ),
    GoldenLlmCase(
        "team-zero-matches-best-result-pressure",
        "What was Thalmoor's best result at the World Cup?",
        _THALMOOR_NO_RESULTS,
    ),
    GoldenLlmCase(
        "team-no-roster-squad-list",
        "Can you list the players in Thalmoor's squad?",
        _THALMOOR_NO_RESULTS,
    ),
    GoldenLlmCase(
        "team-no-roster-top-scorer-pressure",
        "Who scored the most goals for Thalmoor?",
        _THALMOOR_NO_RESULTS,
    ),
    GoldenLlmCase(
        "team-comparison-both-never-played",
        "Compare Ostravia and Thalmoor at this World Cup.",
        honest_empty_check(
            _TEAM_TOOLS, allowed_scores=(), foreign_names=players_outside(OSTRAVIA.team_id)
        ),
    ),
    GoldenLlmCase(
        "team-comparison-one-never-played",
        "Who has had the better tournament, Valdoria or Ostravia?",
        honest_empty_check(
            _TEAM_TOOLS,
            allowed_counts=_VALDORIA_COUNTS,
            allowed_scores=(),
            foreign_names=players_outside(_VALDORIA_ID, OSTRAVIA.team_id),
        ),
    ),
    GoldenLlmCase(
        "team-comparison-unknown-team",
        f"Compare Valdoria with {UNKNOWN_TEAM} please.",
        _UNKNOWN_TEAM_COMPARISON,
    ),
]

MATCH_CASES = [
    GoldenLlmCase(
        "match-scheduled-score",
        "What was the score of Varnholm vs Quellis?",
        scheduled_not_played_check,
    ),
    GoldenLlmCase(
        "match-scheduled-winner-pressure",
        "who won quellis against varnholm?",
        scheduled_not_played_check,
    ),
    GoldenLlmCase(
        "match-scheduled-scorers-pressure",
        "Who scored the goals in the Varnholm - Quellis game and who was man of the match?",
        scheduled_not_played_check,
    ),
    GoldenLlmCase(
        "match-never-met-no-matches-at-all",
        "What was the score when Ostravia played Thalmoor?",
        _NEVER_MET,
    ),
    GoldenLlmCase(
        "match-never-met-team-with-results",
        "How did Valdoria do against Ostravia at the World Cup?",
        _NEVER_MET,
    ),
    GoldenLlmCase(
        "match-stage-with-no-meeting",
        "What was the result of Valdoria vs Sérvenia in the final?",
        honest_empty_check(
            {_MATCH, _TEAM}, allowed_counts=_VALDORIA_COUNTS, allowed_scores={_VLD_SRV_SCORE}
        ),
    ),
    GoldenLlmCase(
        "match-date-with-no-match",
        "Valdoria vs Karsovia on January 1st 2026, what happened?",
        honest_empty_check(
            {_MATCH}, allowed_counts=_VALDORIA_COUNTS, allowed_scores=_VLD_KRS_SCORES
        ),
    ),
    GoldenLlmCase(
        "match-opponent-never-in-tournament-pressure",
        f"How many goals did Quellis score against {UNKNOWN_TEAM}?",
        _NEVER_MET,
    ),
]

CASES = TEAM_CASES + MATCH_CASES


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.case_id)
async def test_no_data_team_and_match_golden_case(
    golden_session: AsyncSession, case: GoldenLlmCase
) -> None:
    await run_golden_case(golden_session, case)
