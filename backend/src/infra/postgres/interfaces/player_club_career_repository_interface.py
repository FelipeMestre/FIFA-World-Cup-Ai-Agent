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

    async def get_career_by_real_player_id(self, real_player_id: int) -> ApprovedClubCareer:
        """Return the club profile and transfer path for an already-known
        `real_player.player_id`, bypassing `player_identity_link` entirely.

        For the `get_player_analysis` Transfermarkt-fallback path, which has
        no World Cup player to gate an approved link through -- the
        `real_player_id` itself is the only identity there is. Raises if
        `real_player_id` doesn't exist; callers only call this after
        resolving the id via `RealPlayerRepositoryInterface.search`.
        """
        ...
