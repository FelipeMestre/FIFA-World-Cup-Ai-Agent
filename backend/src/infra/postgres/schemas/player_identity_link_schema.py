"""Audited match between the synthetic WC2026 roster (`player`) and real
Transfermarkt players (`real_player`). The two id spaces share no key; an
external matching process produces the candidate and this table records the
accepted result.
"""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Numeric, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from src.infra.postgres.schemas.base import Base


class PlayerMatchMethod(StrEnum):
    """How a synthetic roster player was matched to a real Transfermarkt player."""

    EXACT_NAME_DOB = "exact_name_dob"
    EXACT_NAME_TEAM = "exact_name_team"
    FUZZY_NAME = "fuzzy_name"
    MANUAL = "manual"


class PlayerIdentityLinkSchema(Base):
    __tablename__ = "player_identity_link"

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(
        ForeignKey("player.player_id"), nullable=False, unique=True
    )
    real_player_id: Mapped[int] = mapped_column(
        ForeignKey("real_player.player_id"), nullable=False, unique=True
    )
    match_method: Mapped[PlayerMatchMethod] = mapped_column(
        SAEnum(PlayerMatchMethod, name="player_match_method"), nullable=False
    )
    # Null only makes sense when match_method == PlayerMatchMethod.MANUAL;
    # this is documented, not enforced via a DB constraint.
    match_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    reviewed_by_admin: Mapped[bool] = mapped_column(nullable=False, default=False)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
