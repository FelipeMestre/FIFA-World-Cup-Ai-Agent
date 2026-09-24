"""Domain logic backing the admin identity-link review endpoints: list
pending matches, approve, reject. Kept separate from the repository so the
"must currently be pending" invariant is enforced in one place rather than
duplicated across two future API handlers.
"""

from src.domain.ingestion.exceptions.ingestion_exceptions import (
    IdentityLinkAlreadyReviewedError,
    IdentityLinkNotFoundError,
)
from src.domain.ingestion.model.player_identity_link import LinkReviewStatus, PlayerIdentityLink
from src.domain.ingestion.model.player_identity_link_review import PlayerIdentityLinkReview
from src.infra.postgres.interfaces.player_identity_link_repository_interface import (
    PlayerIdentityLinkRepositoryInterface,
)


class PlayerIdentityLinkReviewService:
    def __init__(self, repository: PlayerIdentityLinkRepositoryInterface) -> None:
        self._repository = repository

    async def list_pending(
        self, limit: int = 100, offset: int = 0
    ) -> list[PlayerIdentityLinkReview]:
        return await self._repository.list_pending(limit=limit, offset=offset)

    async def approve(self, link_id: int, admin_user_id: int) -> PlayerIdentityLink:
        await self._require_pending(link_id)
        return await self._repository.update_status(
            link_id, LinkReviewStatus.APPROVED, admin_user_id
        )

    async def reject(self, link_id: int, admin_user_id: int) -> PlayerIdentityLink:
        await self._require_pending(link_id)
        return await self._repository.update_status(
            link_id, LinkReviewStatus.REJECTED, admin_user_id
        )

    async def reassign(
        self, link_id: int, new_real_player_id: int, admin_user_id: int
    ) -> PlayerIdentityLink:
        # No "must be pending" precondition, unlike approve/reject: correcting
        # a match is meant to work on any doubtful link, including one the
        # matching pipeline auto-approved incorrectly.
        return await self._repository.reassign(link_id, new_real_player_id, admin_user_id)

    async def _require_pending(self, link_id: int) -> PlayerIdentityLink:
        link = await self._repository.get(link_id)
        if link is None:
            raise IdentityLinkNotFoundError(f"player_identity_link {link_id} not found")
        if link.status != LinkReviewStatus.PENDING:
            raise IdentityLinkAlreadyReviewedError(
                f"player_identity_link {link_id} is already '{link.status}', not pending"
            )
        return link
