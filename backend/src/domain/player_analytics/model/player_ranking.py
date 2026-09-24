"""Read model for the `query_player_stats` chat tool.

CamelCase aliases match the frontend `PlayerRanking` widget contract.
"""

import re
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Literal

from src.domain.player_analytics.model.player_analysis import _CamelModel

WORLD_CUP_AGE_AS_OF = date(2026, 6, 1)

Position = Literal["GK", "DEF", "MID", "FWD"]


class QueryDataset(StrEnum):
    WORLD_CUP = "world_cup"
    CLUB_SEASONS = "club_seasons"


class FilterOp(StrEnum):
    EQ = "eq"
    GTE = "gte"
    LTE = "lte"


class SortDir(StrEnum):
    ASC = "asc"
    DESC = "desc"


class PlayerStatField(StrEnum):
    POSITION = "position"
    AGE = "age"
    HEIGHT_CM = "height_cm"
    NATIONALITY = "nationality"
    APPEARANCES = "appearances"
    MINUTES = "minutes"
    GOALS = "goals"
    ASSISTS = "assists"
    GOAL_CONTRIBUTIONS = "goal_contributions"
    GOALS_PER90 = "goals_per90"
    ASSISTS_PER90 = "assists_per90"
    GOAL_CONTRIBUTIONS_PER90 = "goal_contributions_per90"
    YELLOW_CARDS = "yellow_cards"
    RED_CARDS = "red_cards"
    STARTS = "starts"
    PENALTY_GOALS = "penalty_goals"
    SAVES = "saves"
    SAVES_PER90 = "saves_per90"
    CLEAN_SHEETS = "clean_sheets"
    GOALS_CONCEDED = "goals_conceded"
    GOALS_CONCEDED_PER90 = "goals_conceded_per90"


FIELD_LABELS: dict[PlayerStatField, str] = {
    PlayerStatField.POSITION: "Position",
    PlayerStatField.AGE: "Age",
    PlayerStatField.HEIGHT_CM: "Height",
    PlayerStatField.NATIONALITY: "Nationality",
    PlayerStatField.APPEARANCES: "Appearances",
    PlayerStatField.MINUTES: "Minutes",
    PlayerStatField.GOALS: "Goals",
    PlayerStatField.ASSISTS: "Assists",
    PlayerStatField.GOAL_CONTRIBUTIONS: "Goals + assists",
    PlayerStatField.GOALS_PER90: "Goals per 90",
    PlayerStatField.ASSISTS_PER90: "Assists per 90",
    PlayerStatField.GOAL_CONTRIBUTIONS_PER90: "Goals + assists per 90",
    PlayerStatField.YELLOW_CARDS: "Yellow cards",
    PlayerStatField.RED_CARDS: "Red cards",
    PlayerStatField.STARTS: "Starts",
    PlayerStatField.PENALTY_GOALS: "Penalty goals",
    PlayerStatField.SAVES: "Saves",
    PlayerStatField.SAVES_PER90: "Saves per 90",
    PlayerStatField.CLEAN_SHEETS: "Clean sheets",
    PlayerStatField.GOALS_CONCEDED: "Goals conceded",
    PlayerStatField.GOALS_CONCEDED_PER90: "Goals conceded per 90",
}

ROSTER_FIELDS = frozenset(
    {
        PlayerStatField.POSITION,
        PlayerStatField.AGE,
        PlayerStatField.HEIGHT_CM,
        PlayerStatField.NATIONALITY,
    }
)
STRING_EQ_FIELDS = frozenset({PlayerStatField.POSITION, PlayerStatField.NATIONALITY})
PER90_FIELDS = frozenset(
    {
        PlayerStatField.GOALS_PER90,
        PlayerStatField.ASSISTS_PER90,
        PlayerStatField.GOAL_CONTRIBUTIONS_PER90,
        PlayerStatField.SAVES_PER90,
        PlayerStatField.GOALS_CONCEDED_PER90,
    }
)
WORLD_CUP_ONLY_FIELDS = frozenset(
    {
        PlayerStatField.STARTS,
        PlayerStatField.PENALTY_GOALS,
        PlayerStatField.SAVES,
        PlayerStatField.SAVES_PER90,
        PlayerStatField.CLEAN_SHEETS,
        PlayerStatField.GOALS_CONCEDED,
        PlayerStatField.GOALS_CONCEDED_PER90,
    }
)
GK_ONLY_FIELDS = frozenset(
    {
        PlayerStatField.SAVES,
        PlayerStatField.SAVES_PER90,
        PlayerStatField.CLEAN_SHEETS,
        PlayerStatField.GOALS_CONCEDED,
        PlayerStatField.GOALS_CONCEDED_PER90,
    }
)
NULLABLE_STAT_FIELDS = frozenset(
    {
        PlayerStatField.SAVES,
        PlayerStatField.SAVES_PER90,
        PlayerStatField.CLEAN_SHEETS,
        PlayerStatField.GOALS_CONCEDED,
        PlayerStatField.GOALS_CONCEDED_PER90,
    }
)
CLUB_FIELDS = frozenset(PlayerStatField) - WORLD_CUP_ONLY_FIELDS
WORLD_CUP_FIELDS = frozenset(PlayerStatField)
FIELD_VALUES = [item.value for item in PlayerStatField]


def parse_season_start_year(label: str) -> int | None:
    """Map a Transfermarkt season label to its start year.

    Accepts `24/25`, `24-25`, `2024/25`, `2024-2025`, or `2024`.
    """
    text = label.strip()
    if not text:
        return None
    two_digit = re.fullmatch(r"(\d{2})[/\-](\d{2})", text)
    if two_digit:
        return 2000 + int(two_digit.group(1))
    four_digit_span = re.fullmatch(r"(\d{4})[/\-](\d{2,4})", text)
    if four_digit_span:
        return int(four_digit_span.group(1))
    year_only = re.fullmatch(r"(\d{4})", text)
    if year_only:
        return int(year_only.group(1))
    return None


def normalize_season_years(labels: list[str]) -> tuple[int, ...] | None:
    years: list[int] = []
    seen: set[int] = set()
    for label in labels:
        year = parse_season_start_year(label)
        if year is None:
            return None
        if year not in seen:
            seen.add(year)
            years.append(year)
    return tuple(sorted(years))


def format_season_label(years: tuple[int, ...]) -> str:
    return " + ".join(f"{year % 100:02d}/{(year + 1) % 100:02d}" for year in years)


def used_fields(
    sort_by: PlayerStatField, filters: tuple["StatFilter", ...]
) -> frozenset[PlayerStatField]:
    return frozenset({sort_by, *(item.field for item in filters)})


def field_allowed_on_dataset(field: PlayerStatField, dataset: QueryDataset) -> bool:
    if dataset == QueryDataset.WORLD_CUP:
        return field in WORLD_CUP_FIELDS
    return field in CLUB_FIELDS


def widget_scope(dataset: QueryDataset) -> Literal["world_cup", "transfermarkt"]:
    if dataset == QueryDataset.WORLD_CUP:
        return "world_cup"
    return "transfermarkt"


@dataclass(frozen=True, slots=True)
class StatFilter:
    field: PlayerStatField
    op: FilterOp
    value: str | int | float


@dataclass(frozen=True, slots=True)
class QueryPlayerStatsRequest:
    dataset: QueryDataset
    sort_by: PlayerStatField
    sort_dir: SortDir
    filters: tuple[StatFilter, ...]
    season_years: tuple[int, ...]
    season_label: str
    competition_id: str | None
    competition_label: str
    limit: int


class PlayerRankingRow(_CamelModel):
    rank: int
    player_id: str
    name: str
    initials: str
    team_code: str
    club_team: str
    position: Literal["GK", "DEF", "MID", "FWD"]
    value: str
    sort_value: float
    appearances: int
    minutes: int
    goals: int
    assists: int
    yellow_cards: int
    red_cards: int
    height_cm: int
    age: int
    starts: int | None = None
    penalty_goals: int | None = None
    saves: int | None = None
    clean_sheets: int | None = None
    goals_conceded: int | None = None


class PlayerRanking(_CamelModel):
    id: str
    scope: Literal["world_cup", "transfermarkt"]
    rank_by: str
    rank_by_label: str
    scope_label: str
    footer_caption: str
    rows: list[PlayerRankingRow]
