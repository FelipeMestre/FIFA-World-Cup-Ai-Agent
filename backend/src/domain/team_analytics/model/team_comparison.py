"""Read model for the `get_team_comparison` chat tool.

Snake_case attributes, camelCase JSON via `_CamelModel`, same wire convention
as `TeamAnalysis` and `PlayerComparison`. One payload feeds both surfaces:
the chat widget reads the two team summaries, `compared_stats`,
`strengths_and_flaws`, and `meetings`; the side panel reads `positions`.
"""

from typing import Literal

from src.domain.team_analytics.model.base import CamelModel as _CamelModel
from src.domain.team_analytics.model.base import ResultLetter, TeamMatchResult, TeamRecord

Position = Literal["GK", "DEF", "MID", "FWD"]
ComparisonSide = Literal["a", "b"]
EdgeKind = Literal["strength", "flaw"]


class TeamRates(_CamelModel):
    goals_per_game: float
    conceded_per_game: float
    xg_for: float
    xg_against: float
    xg_difference: float
    xg_per_game: float
    xg_against_per_game: float
    possession_pct: float
    shots_per_game: float
    shots_on_target_per_game: float
    shot_accuracy_pct: float
    conversion_pct: float
    corners_per_game: float
    fouls_per_game: float
    offsides_per_game: float
    saves: int
    saves_per_game: float
    clean_sheets: int
    clean_sheets_per_game: float


class TeamDisciplineSummary(_CamelModel):
    yellow_cards: int
    red_cards: int
    fouls: int
    yellow_per_match: float


class SquadProfile(_CamelModel):
    """Roster figures are summed from the World Cup squad. The Transfermarkt
    fields are that source's own squad totals, null until a sync matches the
    team, and are not mixed into `average_age` or `total_market_value_eur`.
    """

    roster_size: int
    average_age: float | None
    total_market_value_eur: int
    youngest_age: int | None
    oldest_age: int | None
    under_23_pct: float
    over_30_pct: float
    top_three_value_share_pct: float
    distinct_starters: int
    starter_minutes_share_pct: float
    transfermarkt_average_age: float | None
    transfermarkt_market_value_eur: int | None
    transfermarkt_squad_size: int | None


class GroupOutcome(_CamelModel):
    played: int
    points: int
    goal_difference: int


class SquadLeader(_CamelModel):
    player_id: str
    name: str
    position: Position
    goals: int
    assists: int
    minutes: int


class ComparedTeam(_CamelModel):
    id: str
    code: str
    name: str
    confederation: str
    group_letter: str | None
    manager_name: str | None
    fifa_ranking_pre_tournament: int | None
    elo_rating: int | None
    standing_label: str
    stage_caption: str
    record: TeamRecord
    goal_difference: int
    rates: TeamRates
    discipline: TeamDisciplineSummary
    squad: SquadProfile
    group: GroupOutcome
    match_results: list[TeamMatchResult]
    top_scorer: SquadLeader | None
    top_assister: SquadLeader | None
    most_minutes: SquadLeader | None


class ComparedStat(_CamelModel):
    label: str
    team_a_display: str
    team_b_display: str
    field_display: str
    team_a_value: float
    team_b_value: float
    field_value: float
    higher_is_better: bool
    team_a_is_better: bool
    team_b_is_better: bool


class SideNote(_CamelModel):
    """A strength or flaw big enough to clear the gap threshold and the
    tournament average. `detail` leads with this side's value.
    """

    side: ComparisonSide
    kind: EdgeKind
    label: str
    detail: str


class Meeting(_CamelModel):
    match_id: str
    stage: str
    team_a_score: int
    team_b_score: int
    team_a_result: ResultLetter
    penalty_score: str | None


class ComparisonPlayer(_CamelModel):
    id: str
    name: str
    initials: str
    position: Position
    club: str
    age: int
    height_cm: int
    market_value_eur: int
    caps: int
    appearances: int
    starts: int
    minutes: int
    goals: int
    assists: int
    goals_per90: float
    assists_per90: float
    goal_contributions_per90: float
    yellow_cards: int
    red_cards: int
    penalty_goals: int
    own_goals: int
    clean_sheets: int | None
    saves: int | None
    goals_conceded: int | None
    saves_per90: float | None
    goals_conceded_per90: float | None


class PositionRollup(_CamelModel):
    minutes: int
    market_value_eur: int
    goals: int
    assists: int


class PositionSquad(_CamelModel):
    position: Position
    players: list[ComparisonPlayer]
    rollup: PositionRollup


class PositionGroup(_CamelModel):
    position: Position
    team_a_players: list[ComparisonPlayer]
    team_b_players: list[ComparisonPlayer]
    team_a_rollup: PositionRollup
    team_b_rollup: PositionRollup


class TeamComparison(_CamelModel):
    id: str
    scope_label: str
    team_a: ComparedTeam
    team_b: ComparedTeam
    compared_stats: list[ComparedStat]
    strengths_and_flaws: list[SideNote]
    meetings: list[Meeting]
    positions: list[PositionGroup]
