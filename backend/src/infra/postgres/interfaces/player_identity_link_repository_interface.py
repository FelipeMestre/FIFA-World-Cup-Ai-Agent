from typing import Protocol

from src.domain.ingestion.model.player_identity_candidate import PlayerIdentityCandidate
from src.domain.ingestion.model.player_identity_link import LinkReviewStatus, PlayerIdentityLink
from src.domain.ingestion.model.player_identity_link_review import PlayerIdentityLinkReview
from src.infra.postgres.interfaces.ingestion_repository_interface import UpsertResult


class PlayerIdentityLinkRepositoryInterface(Protocol):
    async def list_by_status(
        self, status: LinkReviewStatus | None, limit: int = 100, offset: int = 0
    ) -> list[PlayerIdentityLinkReview]: ...
    async def count_by_status(self, status: LinkReviewStatus | None) -> int: ...
    async def get(self, link_id: int) -> PlayerIdentityLink | None: ...
    async def update_status(
        self, link_id: int, status: LinkReviewStatus, reviewed_by_user_id: int | None
    ) -> PlayerIdentityLink: ...
    async def reassign(
        self, link_id: int, new_real_player_id: int, admin_user_id: int
    ) -> PlayerIdentityLink: ...
    async def upsert_candidates(
        self, candidates: list[PlayerIdentityCandidate]
    ) -> UpsertResult: ...
    async def delete_all(self) -> int:
        """Deletes every row of `player_identity_link`. Returns the number of
        rows deleted. Used by the identity-link rematch feature to wipe the
        table clean before regenerating it from scratch -- `upsert_candidates`
        alone cannot produce a clean result, since its `ON CONFLICT DO UPDATE`
        leaves a stale row untouched for any player no longer matched.
        """
        ...
