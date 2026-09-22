"""Read model for the `get_player_analysis` chat tool.

Mirrors the frontend's `PlayerSummary` contract (frontend/src/features/chat/
types.ts) field-for-field: attributes are snake_case Python, but every model
aliases to camelCase (`_CamelModel`) so `PlayerAnalysis.model_dump(mode="json",
by_alias=True)` produces the exact shape `WidgetPlayer.data` expects on
the wire, with no reshaping at the tool-handler boundary.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

ResultLetter = Literal["W", "D", "L"]


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class StatChip(_CamelModel):
    label: str
    value: str


class PlayerStatRow(_CamelModel):
    stat: str
    total: str
    per_ninety: str
    # Percentile within position, undefined for stats with no percentile (e.g. minutes).
    percentile: int | None = None


class PlayerBenchmarkRow(_CamelModel):
    label: str
    value: float
    position_average: float


class PlayerAnalysis(_CamelModel):
    # A string, not the raw `player.player_id` int -- matches the
    # frontend's `EntityRef.id: string` and every other entity id in its
    # widget contract.
    id: str
    name: str
    initials: str
    team_code: str
    position: Literal["GK", "DEF", "MID", "FWD"]
    appearances: int
    minutes: int
    scope_label: str
    tier_label: str
    # Filled segments of the 3-step contribution meter, 0-3.
    tier_segments: int
    discipline_label: str
    chips: list[StatChip]
    footer_caption: str
    full_breakdown: list[PlayerStatRow]
    per_ninety_vs_position_average: list[PlayerBenchmarkRow]
