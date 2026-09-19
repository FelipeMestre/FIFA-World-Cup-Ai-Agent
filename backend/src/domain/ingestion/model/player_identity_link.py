"""Domain object mirroring `player_identity_link_schema.py`'s persisted
shape: an audited match between a synthetic WC2026 roster player and a real
Transfermarkt player.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class PlayerMatchMethod(StrEnum):
    """How a synthetic roster player was matched to a real Transfermarkt player."""

    EXACT_NAME_DOB = "exact_name_dob"
    EXACT_NAME_TEAM = "exact_name_team"
    FUZZY_NAME = "fuzzy_name"
    MANUAL = "manual"


class LinkReviewStatus(StrEnum):
    """Tri-state review outcome: a rejection is represented explicitly,
    never by deleting the row.
    """

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class PlayerIdentityLink:
    id: int | None
    player_id: int
    real_player_id: int
    match_method: PlayerMatchMethod
    match_confidence: Decimal | None
    status: LinkReviewStatus
    reviewed_by_user_id: int | None
    created_at: datetime | None = None
