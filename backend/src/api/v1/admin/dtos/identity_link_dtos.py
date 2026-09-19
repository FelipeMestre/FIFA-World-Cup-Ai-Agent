from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from src.domain.ingestion.model.player_identity_link import PlayerIdentityLink


class IdentityLinkResponse(BaseModel):
    id: int
    player_id: int
    real_player_id: int
    match_method: str
    match_confidence: Decimal | None
    status: str
    created_at: datetime | None

    @classmethod
    def from_domain(cls, link: PlayerIdentityLink) -> "IdentityLinkResponse":
        return cls(
            id=link.id,
            player_id=link.player_id,
            real_player_id=link.real_player_id,
            match_method=link.match_method.value,
            match_confidence=link.match_confidence,
            status=link.status.value,
            created_at=link.created_at,
        )
