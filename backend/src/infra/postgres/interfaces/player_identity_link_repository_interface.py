from typing import Protocol

from src.domain.ingestion.model.player_identity_candidate import PlayerIdentityCandidate
from src.domain.ingestion.model.player_identity_link import LinkReviewStatus, PlayerIdentityLink
from src.infra.postgres.interfaces.ingestion_repository_interface import UpsertResult


class PlayerIdentityLinkRepositoryInterface(Protocol):
    async def list_pending(self, limit: int = 100, offset: int = 0) -> list[PlayerIdentityLink]: ...
    async def get(self, link_id: int) -> PlayerIdentityLink | None: ...
    async def update_status(
        self, link_id: int, status: LinkReviewStatus, reviewed_by_user_id: int | None
    ) -> PlayerIdentityLink: ...
    async def upsert_candidates(
        self, candidates: list[PlayerIdentityCandidate]
    ) -> UpsertResult: ...
