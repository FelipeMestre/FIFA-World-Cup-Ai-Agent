from pydantic import BaseModel

from src.domain.teams.model.team import Team


class TeamResponse(BaseModel):
    id: int
    name: str
    fifa_code: str
    group_letter: str
    confederation: str
    fifa_ranking_pre_tournament: int
    elo_rating: int
    manager_name: str

    @classmethod
    def from_domain(cls, team: Team) -> "TeamResponse":
        return cls(
            id=team.id,
            name=team.name,
            fifa_code=team.fifa_code,
            group_letter=team.group_letter,
            confederation=team.confederation,
            fifa_ranking_pre_tournament=team.fifa_ranking_pre_tournament,
            elo_rating=team.elo_rating,
            manager_name=team.manager_name,
        )
