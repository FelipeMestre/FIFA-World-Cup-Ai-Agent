"""Composite read model for the admin review list: a pending
`PlayerIdentityLink` alongside both sides of the match it's proposing, so
the admin can decide without a follow-up lookup for either player.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.ingestion.model.player_identity_link import PlayerIdentityLink
from src.domain.ingestion.model.real_player import RealPlayer
from src.domain.players.model.player import Player


@dataclass(frozen=True, slots=True)
class PlayerIdentityLinkReview:
    link: PlayerIdentityLink
    synthetic_player: Player
    # Player.team_id is a WC2026 national_team id, not a country name --
    # resolved by the repository's join since Player itself (used broadly
    # outside this review context) doesn't carry it.
    synthetic_player_nationality: str
    real_player: RealPlayer
