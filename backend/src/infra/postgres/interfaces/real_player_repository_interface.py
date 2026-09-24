from typing import Protocol

from src.domain.ingestion.model.real_player import RealPlayer


class RealPlayerRepositoryInterface(Protocol):
    async def get(self, player_id: int) -> RealPlayer | None: ...
    async def search(self, query: str, limit: int = 20, offset: int = 0) -> list[RealPlayer]: ...
