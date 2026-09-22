"""Read model for the `get_match_analysis` chat tool.

Mirrors the frontend's `MatchSummary` contract (frontend/src/features/chat/
types.ts) field-for-field: attributes are snake_case Python, but every model
aliases to camelCase (`_CamelModel`) so `MatchAnalysis.model_dump(mode="json",
by_alias=True)` produces the exact shape `MatchWidgetPart.data` expects on
the wire, with no reshaping at the tool-handler boundary.

Two extra fields the frontend type doesn't carry -- `MatchAnalysisAmbiguous`
and `MatchCandidate` -- exist only for the tool-result JSON `content` the
model reads back when the home/away query resolves to more than one plausible
match (see `get_match_analysis.py`); they never reach `widget_data`.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

Position = Literal["GK", "DEF", "MID", "FWD"]
MatchEventKind = Literal["goal", "card", "var", "sub"]


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class TeamRef(_CamelModel):
    code: str
    name: str


class MatchStatRow(_CamelModel):
    label: str
    home_value: str
    away_value: str
    # Home share of the split bar, 0-100.
    home_pct: int


class MatchEvent(_CamelModel):
    minute: str
    kind: MatchEventKind
    team_code: str
    title: str
    detail: str | None = None
    sub_on: str | None = None
    sub_off: str | None = None


class PlayerOfMatch(_CamelModel):
    name: str
    team_code: str
    position: Position
    note: str


class LineupPlayer(_CamelModel):
    number: int
    name: str
    # e.g. "▲ 64'" (on) or "▼ 72'" (off); absent when not substituted.
    mark: str | None = None


class LineupGroup(_CamelModel):
    name: Position | Literal["Subs used"]
    players: list[LineupPlayer]


class TeamLineup(_CamelModel):
    code: str
    name: str
    shape: str
    groups: list[LineupGroup]


class MatchAnalysis(_CamelModel):
    # A string, not the raw `match.match_id` int -- matches the frontend's
    # `EntityRef.id: string` and every other entity id in its widget
    # contract.
    id: str
    stage_label: str
    date_label: str
    venue_label: str | None = None
    home_team: TeamRef
    away_team: TeamRef
    home_score: int
    away_score: int
    status_label: str
    home_scorers: str
    away_scorers: str
    stats: list[MatchStatRow]
    events: list[MatchEvent]
    player_of_match: PlayerOfMatch
    timeline: list[MatchEvent]
    lineups: list[TeamLineup]
    footer_caption: str


class MatchCandidate(_CamelModel):
    """One plausible match for an ambiguous home/away (+ optional stage/date)
    query -- enough for the model to describe the choice back to the user in
    its next reply, not a full `MatchAnalysis`.
    """

    id: str
    stage_label: str
    date_label: str
    home_team_code: str
    away_team_code: str
    score: str


class MatchAnalysisAmbiguous(_CamelModel):
    """Returned instead of a `MatchAnalysis` when the home/away (+ optional
    stage/date) query resolves to 2+ matches. Never reaches `widget_data` --
    `get_match_analysis`'s handler serializes this into the tool result's
    `content` string so the model can ask the user to disambiguate, reusing
    the existing tool-result-to-model round-trip.
    """

    candidates: list[MatchCandidate]
