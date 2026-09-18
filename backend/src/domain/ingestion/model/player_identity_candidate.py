"""A match produced by the identity-matching pipeline before persistence --
not yet a `PlayerIdentityLink` row. Kept as an independently importable,
lightweight type so the matching service (a pure function, no I/O) does not
need to depend on the persisted-link shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from src.domain.ingestion.model.player_identity_link import PlayerMatchMethod


@dataclass(frozen=True, slots=True)
class PlayerIdentityCandidate:
    player_id: int
    real_player_id: int
    match_method: PlayerMatchMethod
    match_confidence: Decimal
