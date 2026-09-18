from typing import Protocol

from src.domain.matches.model.match import Match


class MatchRepositoryInterface(Protocol):
    async def get(self, match_id: int) -> Match | None: ...
    async def list(self, limit: int = 100, offset: int = 0) -> list[Match]: ...
