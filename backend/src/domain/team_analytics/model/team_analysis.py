"""Read model for the `get_team_analysis` chat tool.

Mirrors the frontend's `TeamSummary` contract (frontend/src/features/chat/
types.ts) field-for-field: attributes are snake_case Python, but every model
aliases to camelCase (`_CamelModel`) so `TeamAnalysis.model_dump(mode="json",
by_alias=True)` produces the exact shape `TeamWidgetPart.data` expects on
the wire, with no reshaping at the tool-handler boundary.
"""

from src.domain.team_analytics.model.base import (
    CamelModel,
    TeamMatchResult,
    TeamRecord,
)
from src.domain.team_analytics.model.team_comparison import (
    GroupOutcome,
    PositionSquad,
    SquadLeader,
    SquadProfile,
)

_CamelModel = CamelModel


class TeamGoalsByMatch(_CamelModel):
    opponent_code: str
    goals_for: int
    goals_against: int


class StatWithFieldAverage(_CamelModel):
    label: str
    value: str
    field_value: str
    # e.g. "▲ 8.4" or "▼ 1.2" -- always carries the glyph, never color alone.
    delta: str


class TeamDiscipline(_CamelModel):
    yellow_cards: int
    red_cards: int
    fouls: int
    yellow_per_match: float
    field_yellow_per_match: float


class TeamAnalysis(_CamelModel):
    # A string, not the raw `national_team.team_id` int -- matches the
    # frontend's `EntityRef.id: string` and every other entity id in its
    # widget contract.
    id: str
    code: str
    name: str
    scope_label: str
    standing_label: str
    record: TeamRecord
    goal_difference: int
    conceded_per_game: float
    clean_sheets: int
    avg_possession_pct: float
    goals_by_match: list[TeamGoalsByMatch]
    tournament_averages: list[StatWithFieldAverage]
    match_results: list[TeamMatchResult]
    discipline: TeamDiscipline
    stage_caption: str
    confederation: str
    group_letter: str | None
    manager_name: str | None
    fifa_ranking_pre_tournament: int | None
    squad: SquadProfile
    group: GroupOutcome
    top_scorer: SquadLeader | None
    top_assister: SquadLeader | None
    most_minutes: SquadLeader | None
    positions: list[PositionSquad]
