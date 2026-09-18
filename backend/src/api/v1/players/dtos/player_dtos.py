from datetime import date

from pydantic import BaseModel

from src.domain.players.model.player import Player


class PlayerResponse(BaseModel):
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

    @classmethod
    def from_domain(cls, player: Player) -> "PlayerResponse":
        return cls(
            id=player.id,
            team_id=player.team_id,
            name=player.name,
            position=player.position,
            club_team=player.club_team,
            market_value_eur=player.market_value_eur,
            caps=player.caps,
            date_of_birth=player.date_of_birth,
            height_cm=player.height_cm,
            goals=player.goals,
        )
