"""Read model for the `get_player_analysis` chat tool.

Mirrors the frontend's `PlayerSummary` contract (frontend/src/features/chat/
types.ts) field-for-field: attributes are snake_case Python, but every model
aliases to camelCase (`_CamelModel`) so `PlayerAnalysis.model_dump(mode="json",
by_alias=True)` produces the exact shape `WidgetPlayer.data` expects on
the wire, with no reshaping at the tool-handler boundary.
"""

from dataclasses import dataclass
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
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


class PlayerClubProfile(_CamelModel):
    """Transfermarkt profile attached through an approved identity link.

    Separate from the World Cup block: these values never feed percentile math.
    """

    preferred_foot: str | None
    sub_position: str | None
    height_cm: int | None
    date_of_birth: date | None
    citizenship: str | None
    current_club: str | None
    market_value_eur: int | None
    highest_market_value_eur: int | None
    international_caps: int | None
    international_goals: int | None


class PlayerTransfer(_CamelModel):
    transfer_date: date
    season: str | None
    from_club: str
    to_club: str
    fee_eur: int | None
    market_value_eur: int | None


class PlayerSeasonStat(_CamelModel):
    """One competition inside a club season, with the club he was at that year.

    These figures are not mixed into the World Cup percentile block.
    """

    season: str
    team: str | None
    competition_id: str
    competition: str
    appearances: int
    minutes: int
    goals: int
    assists: int
    yellow_cards: int
    red_cards: int


@dataclass(frozen=True, slots=True)
class ApprovedClubCareer:
    profile: PlayerClubProfile
    transfers: tuple[PlayerTransfer, ...]
    career_seasons: tuple[PlayerSeasonStat, ...]


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
    # None when no approved `player_identity_link` exists. Transfers stay
    # empty in that case; an approved link with no moves is a profile and [].
    club_profile: PlayerClubProfile | None = None
    transfers: list[PlayerTransfer] = Field(default_factory=list)
    career_seasons: list[PlayerSeasonStat] = Field(default_factory=list)
