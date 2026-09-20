from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class NationalTeam:
    id: int
    name: str
    confederation: str
    fifa_code: str | None = None
    group_letter: str | None = None
    fifa_ranking_pre_tournament: int | None = None
    elo_rating: int | None = None
    manager_name: str | None = None
    transfermarkt_id: int | None = None
    squad_size: int | None = None
    average_age: Decimal | None = None
    total_market_value_eur: int | None = None
    url: str | None = None
