"""Read model for the `get_player_ranking` chat tool.

CamelCase aliases match the frontend `PlayerRanking` widget contract.
"""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Literal

from src.domain.player_analytics.model.player_analysis import _CamelModel

WORLD_CUP_AGE_AS_OF = date(2026, 6, 1)

Position = Literal["GK", "DEF", "MID", "FWD"]


class RankingScope(StrEnum):
    WORLD_CUP = "world_cup"
    TRANSFERMARKT = "transfermarkt"


class SeasonWindow(StrEnum):
    LATEST = "latest"
    LAST_THREE = "last_three"


class RankBy(StrEnum):
    GOALS = "goals"
    ASSISTS = "assists"
    GOAL_CONTRIBUTIONS = "goal_contributions"
    GOALS_PER90 = "goals_per90"
    ASSISTS_PER90 = "assists_per90"
    GOAL_CONTRIBUTIONS_PER90 = "goal_contributions_per90"
    PENALTY_GOALS = "penalty_goals"
    MINUTES = "minutes"
    APPEARANCES = "appearances"
    STARTS = "starts"
    YELLOW_CARDS = "yellow_cards"
    RED_CARDS = "red_cards"
    FEWEST_YELLOW_CARDS = "fewest_yellow_cards"
    FEWEST_RED_CARDS = "fewest_red_cards"
    SAVES = "saves"
    SAVES_PER90 = "saves_per90"
    CLEAN_SHEETS = "clean_sheets"
    GOALS_CONCEDED = "goals_conceded"
    GOALS_CONCEDED_PER90 = "goals_conceded_per90"


RANK_BY_LABELS: dict[RankBy, str] = {
    RankBy.GOALS: "Goals",
    RankBy.ASSISTS: "Assists",
    RankBy.GOAL_CONTRIBUTIONS: "Goals + assists",
    RankBy.GOALS_PER90: "Goals per 90",
    RankBy.ASSISTS_PER90: "Assists per 90",
    RankBy.GOAL_CONTRIBUTIONS_PER90: "Goals + assists per 90",
    RankBy.PENALTY_GOALS: "Penalty goals",
    RankBy.MINUTES: "Minutes",
    RankBy.APPEARANCES: "Appearances",
    RankBy.STARTS: "Starts",
    RankBy.YELLOW_CARDS: "Yellow cards",
    RankBy.RED_CARDS: "Red cards",
    RankBy.FEWEST_YELLOW_CARDS: "Fewest yellow cards",
    RankBy.FEWEST_RED_CARDS: "Fewest red cards",
    RankBy.SAVES: "Saves",
    RankBy.SAVES_PER90: "Saves per 90",
    RankBy.CLEAN_SHEETS: "Clean sheets",
    RankBy.GOALS_CONCEDED: "Goals conceded",
    RankBy.GOALS_CONCEDED_PER90: "Goals conceded per 90",
}

WORLD_CUP_ONLY_RANK_BY = frozenset(
    {
        RankBy.PENALTY_GOALS,
        RankBy.STARTS,
        RankBy.SAVES,
        RankBy.SAVES_PER90,
        RankBy.CLEAN_SHEETS,
        RankBy.GOALS_CONCEDED,
        RankBy.GOALS_CONCEDED_PER90,
    }
)

GK_ONLY_RANK_BY = frozenset(
    {
        RankBy.SAVES,
        RankBy.SAVES_PER90,
        RankBy.CLEAN_SHEETS,
        RankBy.GOALS_CONCEDED,
        RankBy.GOALS_CONCEDED_PER90,
    }
)

ASCENDING_RANK_BY = frozenset(
    {
        RankBy.FEWEST_YELLOW_CARDS,
        RankBy.FEWEST_RED_CARDS,
        RankBy.GOALS_CONCEDED,
        RankBy.GOALS_CONCEDED_PER90,
    }
)

PER90_RANK_BY = frozenset(
    {
        RankBy.GOALS_PER90,
        RankBy.ASSISTS_PER90,
        RankBy.GOAL_CONTRIBUTIONS_PER90,
        RankBy.SAVES_PER90,
        RankBy.GOALS_CONCEDED_PER90,
    }
)


@dataclass(frozen=True, slots=True)
class PlayerRankingRequest:
    scope: RankingScope
    rank_by: RankBy
    position: Position | None
    age_min: int | None
    age_max: int | None
    height_min_cm: int | None
    height_max_cm: int | None
    nationality: str | None
    season_window: SeasonWindow | None
    competition_id: str | None
    competition_label: str
    limit: int
    min_appearances: int | None = None
    min_minutes: int | None = None
    min_goals: int | None = None
    min_assists: int | None = None


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
