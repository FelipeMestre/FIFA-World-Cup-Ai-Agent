from typing import Protocol

from src.domain.national_teams.model.national_team import NationalTeam


class NationalTeamRepositoryInterface(Protocol):
    async def get(self, team_id: int) -> NationalTeam | None: ...
    async def list(self, limit: int = 100, offset: int = 0) -> list[NationalTeam]: ...
