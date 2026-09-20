from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class NationalTeam:
    id: int
    name: str
    fifa_code: str
    group_letter: str
    confederation: str
    fifa_ranking_pre_tournament: int
    elo_rating: int
    manager_name: str
    real_national_team_id: int | None = None
    squad_size: int | None = None
    average_age: Decimal | None = None
    total_market_value_eur: int | None = None
    url: str | None = None
