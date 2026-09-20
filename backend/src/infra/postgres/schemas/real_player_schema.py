"""Transfermarkt player-centric data: profile, valuations, transfers, and
aggregated season stats.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.infra.postgres.schemas.base import Base


class RealPlayerSchema(Base):
    """Player profile (source: Transfermarkt player export)."""

    __tablename__ = "real_player"

    player_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    first_name: Mapped[str] = mapped_column(nullable=False)
    last_name: Mapped[str] = mapped_column(nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(nullable=True)
    country_of_birth: Mapped[str | None] = mapped_column(nullable=True)
    country_of_citizenship: Mapped[str | None] = mapped_column(nullable=True)
    position: Mapped[str] = mapped_column(nullable=False)
    sub_position: Mapped[str | None] = mapped_column(nullable=True)
    foot: Mapped[str | None] = mapped_column(nullable=True)
    height_cm: Mapped[int | None] = mapped_column(nullable=True)
    current_club_id: Mapped[int | None] = mapped_column(
        ForeignKey("real_club.club_id"), nullable=True
    )
    current_national_team_id: Mapped[int | None] = mapped_column(
        ForeignKey("national_team.real_national_team_id"), nullable=True
    )
    international_caps: Mapped[int | None] = mapped_column(nullable=True)
    international_goals: Mapped[int | None] = mapped_column(nullable=True)
    market_value_eur: Mapped[int | None] = mapped_column(nullable=True)
    highest_market_value_eur: Mapped[int | None] = mapped_column(nullable=True)
    contract_expiration_date: Mapped[date | None] = mapped_column(nullable=True)
    profile_url: Mapped[str] = mapped_column(nullable=False)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RealPlayerValuationSchema(Base):
    """Historical market-value snapshots (source: Transfermarkt player valuations export).

    Surrogate `id` primary key, plus a `(real_player_id, valuation_date)`
    unique constraint the ingestion upsert targets via `ON CONFLICT`: a
    later sync overwrites an earlier same-date valuation for the same
    player rather than accumulating duplicates.
    """

    __tablename__ = "real_player_valuation"
    __table_args__ = (UniqueConstraint("real_player_id", "valuation_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    real_player_id: Mapped[int] = mapped_column(ForeignKey("real_player.player_id"), nullable=False)
    valuation_date: Mapped[date] = mapped_column(nullable=False)
    market_value_eur: Mapped[int] = mapped_column(nullable=False)
    club_name_at_time: Mapped[str | None] = mapped_column(nullable=True)


class RealTransferSchema(Base):
    """Transfer history (source: Transfermarkt transfers export).

    `transfer_date` is kept as-is from upstream, including inconsistent
    future dates (e.g. 2028/2030) present in the source data -- no CHECK
    constraint is applied. A `(real_player_id, transfer_date)` unique
    constraint backs the ingestion upsert's `ON CONFLICT` target.
    """

    __tablename__ = "real_transfer"
    __table_args__ = (UniqueConstraint("real_player_id", "transfer_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    real_player_id: Mapped[int] = mapped_column(ForeignKey("real_player.player_id"), nullable=False)
    transfer_date: Mapped[date] = mapped_column(nullable=False)
    transfer_season: Mapped[str | None] = mapped_column(nullable=True)
    from_club_id: Mapped[int | None] = mapped_column(ForeignKey("real_club.club_id"), nullable=True)
    to_club_id: Mapped[int | None] = mapped_column(ForeignKey("real_club.club_id"), nullable=True)
    from_club_name: Mapped[str] = mapped_column(nullable=False)
    to_club_name: Mapped[str] = mapped_column(nullable=False)
    transfer_fee_eur: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    market_value_at_transfer_eur: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)


class RealPlayerSeasonStatSchema(Base):
    """Per-player, per-season, per-competition aggregate stats.

    Aggregated at ingestion time from Transfermarkt's `appearances.csv`
    (one row per appearance) -- this table only ever holds grouped season
    totals, never individual match-level appearances.
    """

    __tablename__ = "real_player_season_stat"
    __table_args__ = (UniqueConstraint("real_player_id", "season", "competition_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    real_player_id: Mapped[int] = mapped_column(ForeignKey("real_player.player_id"), nullable=False)
    season: Mapped[str] = mapped_column(nullable=False)
    competition_id: Mapped[str] = mapped_column(nullable=False)
    appearances: Mapped[int] = mapped_column(nullable=False)
    goals: Mapped[int] = mapped_column(nullable=False)
    assists: Mapped[int] = mapped_column(nullable=False)
    yellow_cards: Mapped[int] = mapped_column(nullable=False)
    red_cards: Mapped[int] = mapped_column(nullable=False)
    minutes_played: Mapped[int] = mapped_column(nullable=False)
