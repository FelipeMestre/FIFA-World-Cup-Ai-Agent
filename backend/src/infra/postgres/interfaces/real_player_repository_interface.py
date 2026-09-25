from typing import Any, Protocol

from src.domain.ingestion.model.real_player import RealPlayer


class RealPlayerRepositoryInterface(Protocol):
    async def get(self, player_id: int) -> RealPlayer | None: ...
    async def search(self, query: str, limit: int = 20, offset: int = 0) -> list[RealPlayer]: ...
    async def list_match_candidates(self) -> list[dict[str, Any]]:
        """Every `real_player` row, shaped exactly as
        `PlayerIdentityMatchingService.match()` requires: `player_id`,
        `first_name`, `last_name`, `date_of_birth` (a `date`, not a string),
        `height_in_cm` (renamed from the persisted `height_cm` column -- the
        matching service reads this exact key name), and
        `current_national_team_id`. Backs the identity-link rematch feature,
        which re-runs matching purely from already-persisted rows.
        """
        ...
