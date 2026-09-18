from typing import Protocol

from src.domain.players.model.player import Player


class PlayerRepositoryInterface(Protocol):
    async def get(self, player_id: int) -> Player | None: ...
    async def list(self, limit: int = 100, offset: int = 0) -> list[Player]: ...
