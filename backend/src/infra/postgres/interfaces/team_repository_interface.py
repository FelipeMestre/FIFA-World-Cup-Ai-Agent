from typing import Protocol

from src.domain.teams.model.team import Team


class TeamRepositoryInterface(Protocol):
    async def get(self, team_id: int) -> Team | None: ...
    async def list(self, limit: int = 100, offset: int = 0) -> list[Team]: ...
