"""Read contract for a synthetic player's approved Transfermarkt career."""

from typing import Protocol

from src.domain.player_analytics.model.player_analysis import ApprovedClubCareer


class PlayerClubCareerRepositoryInterface(Protocol):
    async def get_approved_career(self, player_id: int) -> ApprovedClubCareer | None:
        """Return the club profile and transfer path for `player.player_id`.

        Follows `player_identity_link` only when `status` is approved.
        Pending and rejected links return `None`, so a review change is
        visible on the next tool call. Season totals and World Cup stats
        are not loaded here.
        """
        ...
