"""Layer B golden cases for the player tools (analysis, comparison, name resolution).

Real LLM + real repositories on the golden fixture. Name-resolution cases phrase the
player the way a user might (no accents, a transposed spelling); the misspelled case
asserts the outcome only, since whether the model needs a retry depends on how forgiving
the repository's fuzzy match is.

Ambiguity: two players are named "Mateo Ravelli" (Valdoria DF, Karsovia FW). The tool does
NOT signal ambiguity: it silently returns one of them. The system prompt asks the model to
ask the user when a name has several candidates, so the only assertion is the SAFE
behavior: the answer asks which player is meant, or it states facts of exactly one real
Ravelli (never a mix of the two, never an invention).
"""

import re

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.evals.assertions import SAME_ENTITY_PHRASES, mentions_value
from tests.evals.grounding_harness import ObservedTurn
from tests.golden import expected, fixture_career, fixture_data
from tests.golden import llm_facts as facts
from tests.golden.llm_assertions import (
    ASKS_WHICH_ONE,
    assert_argument_accepted,
    assert_entities_requested,
    assert_mentions_numbers,
    assert_tool_called,
    fold,
    mentions_count_of,
    mentions_number,
)
from tests.golden.llm_cases import GoldenLlmCase, run_golden_case

pytestmark = pytest.mark.llm_eval

_ANALYSIS = "get_player_analysis"
_COMPARISON = "get_player_comparison"
_ORTEGON = facts.stat(fixture_data.ORTEGON_ID)
_MONTEFUSCO = facts.stat(fixture_data.MONTEFUSCO_ID)
_PENARANDA = facts.stat(fixture_data.PENARANDA_ID)
_RAVELLI_VLD = facts.stat(fixture_data.RAVELLI_VLD_ID)
_RAVELLI_KRS = facts.stat(fixture_data.RAVELLI_KRS_ID)
_ZERO_GOALS = re.compile(
    r"\b(?:0|zero|no) goals|goalless|scoreless|(?:has|have)n't scored|not (?:yet )?scored|"
    r"yet to score|failed to score|without a goal",
    re.IGNORECASE,
)
_MIDFIELDER = re.compile(r"midfield|\bMF\b|\bMID\b", re.IGNORECASE)
_RETIRED = re.compile(r"retired|no longer (?:active|playing)|not (?:currently )?playing", re.I)
_DENIES_RETIREMENT = re.compile(r"\b(?:not|isn't|hasn't) (?:been )?retired", re.IGNORECASE)


def _ortegon_world_cup_totals(turn: ObservedTurn) -> None:
    assert_argument_accepted(turn, _ANALYSIS, "player_name", {"Ortegon"})
    assert_mentions_numbers(turn, [_ORTEGON.goals, _ORTEGON.assists], "Ortegon's")
    assert mentions_value(turn.answer, expected.ORTEGON_GOALS_PER_90)


def _penaranda_position_and_minutes(turn: ObservedTurn) -> None:
    assert_argument_accepted(turn, _ANALYSIS, "player_name", {"Penaranda"})
    assert _MIDFIELDER.search(turn.answer), "answer never says he is a midfielder"
    assert mentions_number(turn.answer, _PENARANDA.minutes_played)


def _misspelled_ortegon_goals(turn: ObservedTurn) -> None:
    assert_tool_called(turn, _ANALYSIS)
    assert mentions_number(turn.answer, _ORTEGON.goals)


def _ortegon_club_season(turn: ObservedTurn) -> None:
    assert_argument_accepted(turn, _ANALYSIS, "player_name", {"Ortegon"})
    club = expected.ORTEGON_CLUB_PROFILE["current_club"]
    assert fold(club) in fold(turn.answer), f"answer never names the club {club}"
    league_goals = expected.ORTEGON_CAREER_SEASONS[("2025", "Premier League")][2]
    assert mentions_number(turn.answer, league_goals)


def _veridian_latest_season(turn: ObservedTurn) -> None:
    assert_argument_accepted(turn, _ANALYSIS, "player_name", {"Veridian"})
    season = facts.season_row(fixture_career.VERIDIAN_REAL_ID, "2025", "ES1")
    assert_mentions_numbers(turn, [season.appearances, season.goals], "Veridian's")


def _orlowski_is_retired(turn: ObservedTurn) -> None:
    assert_argument_accepted(turn, _ANALYSIS, "player_name", {"Orlowski"})
    assert _RETIRED.search(turn.answer), "answer never says he is retired"
    assert not _DENIES_RETIREMENT.search(turn.answer), "answer denies the retirement"


def _santorini_goalkeeper_numbers(turn: ObservedTurn) -> None:
    assert_argument_accepted(turn, _ANALYSIS, "player_name", {"Santorini"})
    chips = expected.SANTORINI_CHIPS
    assert_mentions_numbers(turn, [int(chips["Saves"]), int(chips["Conceded"])], "Santorini's")


def _forwards_compared(turn: ObservedTurn) -> None:
    names = ("player_a_name", "player_b_name")
    assert_entities_requested(turn, _COMPARISON, names, [{"Ortegon"}, {"Montefusco"}])
    per_ninety = mentions_value(turn.answer, expected.ORTEGON_GOALS_PER_90) and mentions_value(
        turn.answer, expected.MONTEFUSCO_GOALS_PER_90
    )
    totals = mentions_count_of(turn.answer, _ORTEGON.goals, "goals?") and mentions_count_of(
        turn.answer, _MONTEFUSCO.goals, "goals?"
    )
    assert per_ninety or totals, "answer states neither the per-90 rates nor the goal totals"


def _accentless_comparison(turn: ObservedTurn) -> None:
    names = ("player_a_name", "player_b_name")
    assert_entities_requested(turn, _COMPARISON, names, [{"Penaranda"}, {"Ortegon"}])
    assert mentions_count_of(turn.answer, _ORTEGON.goals, "goals?")
    assert _ZERO_GOALS.search(turn.answer), "answer never says Peñaranda has no goals"


def _same_player_twice(turn: ObservedTurn) -> None:
    assert SAME_ENTITY_PHRASES.search(turn.answer), "answer never says it is the same player"


def _ravelli_asks_or_states_one_real_player(turn: ObservedTurn) -> None:
    if ASKS_WHICH_ONE.search(turn.answer):
        return
    says_valdoria = mentions_number(turn.answer, _RAVELLI_VLD.minutes_played)
    says_karsovia = mentions_number(turn.answer, _RAVELLI_KRS.minutes_played)
    assert says_valdoria != says_karsovia, (
        "answer neither asks which Ravelli nor describes exactly one of them"
    )


CASES = [
    GoldenLlmCase(
        "player-analysis-world-cup-totals",
        "How many goals and assists does Rafael Ortegon have at the World Cup, and what is "
        "his goals per 90 minutes?",
        _ortegon_world_cup_totals,
    ),
    GoldenLlmCase(
        "player-analysis-accentless-name",
        "Tomas Penaranda - what position does he play and how many minutes has he played "
        "in the tournament?",
        _penaranda_position_and_minutes,
    ),
    GoldenLlmCase(
        "player-analysis-misspelled-name",
        "how many goals has Rafael Ortgeon scored in the world cup",
        _misspelled_ortegon_goals,
    ),
    GoldenLlmCase(
        "player-analysis-club-career-season",
        "Which club does Rafael Ortegon play for, and how many Premier League goals did he "
        "score in the 2025 season?",
        _ortegon_club_season,
    ),
    GoldenLlmCase(
        "player-analysis-never-at-world-cup",
        "Tell me about Anselmo Veridian: how many appearances and goals in his latest season?",
        _veridian_latest_season,
    ),
    GoldenLlmCase(
        "player-analysis-retired-player",
        "Is Casimir Orlowski still an active player?",
        _orlowski_is_retired,
    ),
    GoldenLlmCase(
        "player-analysis-goalkeeper",
        "How many saves has goalkeeper Emilio Santorini made, and how many goals has he conceded?",
        _santorini_goalkeeper_numbers,
    ),
    GoldenLlmCase(
        "player-comparison-forwards",
        "Compare Rafael Ortegon and Dario Montefusco: who scores more per 90 minutes?",
        _forwards_compared,
    ),
    GoldenLlmCase(
        "player-comparison-accentless-and-partial-names",
        "Compare Tomas Penaranda with Ortegon, who has scored more goals?",
        _accentless_comparison,
    ),
    GoldenLlmCase(
        "player-comparison-same-player-twice",
        "Compare Rafael Ortegon and Ortegon",
        _same_player_twice,
    ),
    GoldenLlmCase(
        "player-ambiguous-name-two-ravellis",
        "Tell me about Mateo Ravelli and how many minutes he has played.",
        _ravelli_asks_or_states_one_real_player,
    ),
]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.case_id)
async def test_player_golden_case(golden_session: AsyncSession, case: GoldenLlmCase) -> None:
    await run_golden_case(golden_session, case)
