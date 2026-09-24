"""Domain object mirroring `real_player_schema.py`'s persisted shape: a
Transfermarkt player profile, independent of whether it links to a WC2026
roster player.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True, slots=True)
class RealPlayer:
    player_id: int
    first_name: str
    last_name: str
    date_of_birth: date | None
    country_of_birth: str | None
    country_of_citizenship: str | None
    position: str
    sub_position: str | None
    foot: str | None
    height_cm: int | None
    current_club_id: int | None
    current_national_team_id: int | None
    international_caps: int | None
    international_goals: int | None
    market_value_eur: int | None
    highest_market_value_eur: int | None
    contract_expiration_date: date | None
    profile_url: str
    last_synced_at: datetime
