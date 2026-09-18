from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class Player:
    id: int
    team_id: int
    name: str
    position: str
    club_team: str
    market_value_eur: int
    caps: int
    date_of_birth: date
    height_cm: int
    goals: int
