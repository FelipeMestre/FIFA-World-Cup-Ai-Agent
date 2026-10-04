"""Layer B no-data cases for the player tools (real LLM, real repositories).

Entities come from `fixture_empty`: Orin Tavish has a stat row of zeros and an approved link
to a career without seasons or transfers; Zeno Quillfeather is a goalkeeper with 0 minutes
and unmeasured saves; Wendell Thorncastle is a Transfermarkt record without club, seasons or
transfers. Honest means "zero / not recorded / no career data"; invented means a count other
than zero, a club the player was never linked to, a transfer fee, or a player of another team.

Not repeated here (already in `test_llm_unanswerable.py`): unknown player lookup, weight and
shots not provided. Premise-pressure cases presuppose data that does not exist ("his last
transfer fee", "the Ostravia keeper's saves"); the answer must correct the premise.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.golden import fixture_data
from tests.golden import llm_facts as facts
from tests.golden.fixture_data import StatSeed
from tests.golden.fixture_empty import OSTRAVIA
from tests.golden.llm_cases import GoldenLlmCase, run_golden_case
from tests.golden.llm_no_data import (
    ZERO_ONLY,
    honest_empty_check,
    players_outside,
    team_names_and_clubs,
)
from tests.golden.no_data_cases import UNKNOWN_PLAYER

pytestmark = pytest.mark.llm_eval

_ANALYSIS = "get_player_analysis"
_COMPARISON = "get_player_comparison"
_TEAM = "get_team_analysis"
_PLAYER_TOOLS = {_ANALYSIS, _COMPARISON}
_OSTRAVIA_CLUBS = team_names_and_clubs(OSTRAVIA.team_name)
_FOREIGN_TO_OSTRAVIA = players_outside(OSTRAVIA.team_id)


def _counts(*seeds: StatSeed) -> set[float]:
    """Every count the fixture really holds for these players, plus zero."""
    values = {*ZERO_ONLY}
    for seed in seeds:
        values |= {seed.matches_played, seed.minutes_played, seed.goals, seed.assists}
        values |= {seed.yellow_cards, seed.red_cards}
        values |= {v for v in (seed.saves, seed.clean_sheets, seed.goals_conceded) if v is not None}
    return values


_ORTEGON_TEAM_ID = facts.player(fixture_data.ORTEGON_ID).team_id
_ORTEGON_AND_ZERO = _counts(facts.stat(fixture_data.ORTEGON_ID))
_SANTORINI_AND_ZERO = _counts(facts.stat(fixture_data.SANTORINI_ID))


def _about(tool: str, surname: str):
    return (tool, "player_name", {surname})


def _player_check(surname: str, **knobs):
    return honest_empty_check(
        {_ANALYSIS},
        argument=_about(_ANALYSIS, surname),
        foreign_names=_FOREIGN_TO_OSTRAVIA,
        **knobs,
    )


ZERO_STAT_CASES = [
    GoldenLlmCase(
        "player-zero-minutes-goals",
        "How many goals has Orin Tavish scored at the World Cup?",
        _player_check("Tavish"),
    ),
    GoldenLlmCase(
        "player-zero-minutes-misspelled",
        "how many minuts did orin tavich play and did he start any game",
        honest_empty_check({_ANALYSIS}, foreign_names=_FOREIGN_TO_OSTRAVIA),
    ),
    GoldenLlmCase(
        "player-unmeasured-goalkeeper-saves",
        "How many saves has Zeno Quillfeather made?",
        _player_check("Quillfeather"),
    ),
    GoldenLlmCase(
        "player-unmeasured-goalkeeper-clean-sheets",
        "What are the clean sheets and goals conceded of goalkeeper Zeno Quillfeather?",
        _player_check("Quillfeather"),
    ),
    GoldenLlmCase(
        "player-unmeasured-goalkeeper-saves-pressure",
        "How many saves did the Ostravia keeper make?",
        honest_empty_check(
            {_ANALYSIS, _TEAM}, foreign_names=_FOREIGN_TO_OSTRAVIA, allowed_counts=ZERO_ONLY
        ),
    ),
]

CAREER_CASES = [
    GoldenLlmCase(
        "player-empty-career-clubs",
        "Which clubs has Orin Tavish played for during his career?",
        _player_check("Tavish", allowed_clubs=_OSTRAVIA_CLUBS, no_money=True),
    ),
    GoldenLlmCase(
        "player-empty-career-transfer-fee-pressure",
        "How much was Orin Tavish's last transfer fee and which club paid it?",
        _player_check("Tavish", allowed_clubs=_OSTRAVIA_CLUBS, no_money=True),
    ),
    GoldenLlmCase(
        "player-career-record-without-club",
        "Tell me about Wendell Thorncastle's career and current club.",
        _player_check("Thorncastle", allowed_clubs=set(), no_money=True),
    ),
    GoldenLlmCase(
        "player-career-record-best-season-pressure",
        "In which season did Wendell Thorncastle score the most goals?",
        _player_check("Thorncastle", allowed_clubs=set(), no_money=True),
    ),
    GoldenLlmCase(
        "player-career-record-market-value-pressure",
        "what is wendell thorncastle worth, and who is he playing for these days?",
        _player_check("Thorncastle", allowed_clubs=set(), no_money=True),
    ),
]

COMPARISON_CASES = [
    GoldenLlmCase(
        "comparison-with-zero-minute-player",
        "Compare Orin Tavish with Rafael Ortegon.",
        honest_empty_check(
            {_COMPARISON},
            allowed_counts=_ORTEGON_AND_ZERO,
            foreign_names=players_outside(
                OSTRAVIA.team_id, facts.player(fixture_data.ORTEGON_ID).team_id
            ),
        ),
    ),
    GoldenLlmCase(
        "comparison-goalkeepers-unmeasured-saves",
        "Who is the better goalkeeper, Zeno Quillfeather or Emilio Santorini? Compare their saves.",
        honest_empty_check(
            {_COMPARISON, _ANALYSIS},
            allowed_counts=_SANTORINI_AND_ZERO,
            foreign_names=players_outside(
                OSTRAVIA.team_id, facts.player(fixture_data.SANTORINI_ID).team_id
            ),
        ),
    ),
    GoldenLlmCase(
        "comparison-unknown-first-player",
        f"Who is better, {UNKNOWN_PLAYER} or Rafael Ortegon?",
        honest_empty_check({_COMPARISON, _ANALYSIS}, allowed_counts=_ORTEGON_AND_ZERO),
    ),
    GoldenLlmCase(
        "comparison-career-only-player",
        "Compare Wendell Thorncastle and Rafael Ortegon by goals per 90.",
        honest_empty_check({_COMPARISON, _ANALYSIS}, allowed_counts=_ORTEGON_AND_ZERO),
    ),
]

CASES = ZERO_STAT_CASES + CAREER_CASES + COMPARISON_CASES


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.case_id)
async def test_no_data_player_golden_case(
    golden_session: AsyncSession, case: GoldenLlmCase
) -> None:
    await run_golden_case(golden_session, case)
