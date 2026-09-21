"""Read model for the `get_team_analysis` chat tool.

Mirrors the frontend's `TeamSummary` contract (frontend/src/features/chat/
types.ts) field-for-field: attributes are snake_case Python, but every model
aliases to camelCase (`_CamelModel`) so `TeamAnalysis.model_dump(mode="json",
by_alias=True)` produces the exact shape `TeamWidgetPart.data` expects on
the wire, with no reshaping at the tool-handler boundary.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

ResultLetter = Literal["W", "D", "L"]


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class TeamRecord(_CamelModel):
    won: int
    drawn: int
    lost: int
    goals_for: int
    goals_against: int


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


class TeamMatchResult(_CamelModel):
    stage: str
    opponent_code: str
    opponent_name: str
    score: str
    result: ResultLetter


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
