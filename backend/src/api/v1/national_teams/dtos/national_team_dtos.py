from decimal import Decimal

from pydantic import BaseModel

from src.domain.national_teams.model.national_team import NationalTeam


class NationalTeamResponse(BaseModel):
    id: int
    name: str
    confederation: str
    fifa_code: str | None
    group_letter: str | None
    fifa_ranking_pre_tournament: int | None
    elo_rating: int | None
    manager_name: str | None
    transfermarkt_id: int | None
    squad_size: int | None
    average_age: Decimal | None
    total_market_value_eur: int | None
    url: str | None

    @classmethod
    def from_domain(cls, national_team: NationalTeam) -> "NationalTeamResponse":
        return cls(
            id=national_team.id,
            name=national_team.name,
            confederation=national_team.confederation,
            fifa_code=national_team.fifa_code,
            group_letter=national_team.group_letter,
            fifa_ranking_pre_tournament=national_team.fifa_ranking_pre_tournament,
            elo_rating=national_team.elo_rating,
            manager_name=national_team.manager_name,
            transfermarkt_id=national_team.transfermarkt_id,
            squad_size=national_team.squad_size,
            average_age=national_team.average_age,
            total_market_value_eur=national_team.total_market_value_eur,
            url=national_team.url,
        )
