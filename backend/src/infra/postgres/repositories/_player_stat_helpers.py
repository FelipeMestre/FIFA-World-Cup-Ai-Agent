"""Pure, DB-independent helpers shared by `player_analytics_repository.py`
and `_player_analysis_view.py` -- position normalization, per-90 rate math,
and percentile ranking. Extracted out of `player_analytics_repository.py`
once `get_player_comparison` pushed that file past the project's 400-line
cap (see AGENTS.md's file-size rule), so both `get_player_analysis` and
`get_player_comparison` read from one place rather than duplicating this
logic.

`player`/`player_stat.position` stores an abbreviated code (`"FW"`, `"DF"`,
`"MF"`, `"GK"`, confirmed against this codebase's own integration-test
fixtures) rather than the frontend's `GK`/`DEF`/`MID`/`FWD` literals, so
`_normalize_position` maps by first letter rather than an exact lookup --
tolerant of an upstream `"Defender"`/`"Forward"`-style spelling too, since
nothing elsewhere in the codebase pins the exact upstream spelling down.
"""

from typing import Literal

from src.infra.postgres.schemas.player_schema import PlayerStatSchema

Position = Literal["GK", "DEF", "MID", "FWD"]

_POSITION_BY_FIRST_LETTER: dict[str, Position] = {
    "G": "GK",
    "D": "DEF",
    "M": "MID",
    "F": "FWD",
}
_FIRST_LETTER_BY_POSITION: dict[Position, str] = {
    letter_position: letter for letter, letter_position in _POSITION_BY_FIRST_LETTER.items()
}


def normalize_position(raw_position: str) -> Position:
    first_letter = raw_position.strip()[:1].upper()
    return _POSITION_BY_FIRST_LETTER.get(first_letter, "MID")


def first_letter_for_position(position: Position) -> str:
    return _FIRST_LETTER_BY_POSITION[position]


def player_initials(name: str) -> str:
    parts = [p for p in name.split() if p]
    if not parts:
        return "??"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def per_ninety(total: int, minutes_played: int) -> float:
    if minutes_played <= 0:
        return 0.0
    return round(total * 90 / minutes_played, 2)


def percentile(value: float, population: list[float]) -> int:
    """Midpoint percentile rank of `value` within `population` (which
    includes the player's own value): the share of the population strictly
    below `value`, plus half the share exactly equal to it, as a 0-100
    integer. Returns 0 for an empty population rather than dividing by zero.
    """
    if not population:
        return 0
    below = sum(1 for v in population if v < value)
    equal = sum(1 for v in population if v == value)
    rank = (below + 0.5 * equal) / len(population) * 100
    return round(rank)


def average(values: list[float]) -> float:
    return round(sum(values) / len(values), 2) if values else 0.0


def goal_contribution_per90(row: PlayerStatSchema) -> float:
    return per_ninety(row.goals + row.assists, row.minutes_played)


def saves_per90(row: PlayerStatSchema) -> float:
    return per_ninety(row.saves or 0, row.minutes_played)


def goal_per90(row: PlayerStatSchema) -> float:
    return per_ninety(row.goals, row.minutes_played)


def assist_per90(row: PlayerStatSchema) -> float:
    return per_ninety(row.assists, row.minutes_played)


def conceded_per90(row: PlayerStatSchema) -> float:
    return per_ninety(row.goals_conceded or 0, row.minutes_played)


def clean_sheets_per90(row: PlayerStatSchema) -> float:
    return per_ninety(row.clean_sheets or 0, row.minutes_played)


def yellow_cards_per90(row: PlayerStatSchema) -> float:
    return per_ninety(row.yellow_cards, row.minutes_played)


def red_cards_per90(row: PlayerStatSchema) -> float:
    return per_ninety(row.red_cards, row.minutes_played)
