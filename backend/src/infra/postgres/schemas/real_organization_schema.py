"""Transfermarkt club and national-team reference data.

These tables mirror Transfermarkt entities and are the target of the
`current_club_id` / `current_national_team_id` foreign keys on `real_player`
and the `real_national_team_id` foreign key on the existing `team` table.
"""

from decimal import Decimal

from sqlalchemy import Numeric
from sqlalchemy.orm import Mapped, mapped_column

from src.infra.postgres.schemas.base import Base


class RealClubSchema(Base):
    """Club reference data (source: Transfermarkt club export)."""

    __tablename__ = "real_club"

    club_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    club_code: Mapped[str] = mapped_column(nullable=False)
    name: Mapped[str] = mapped_column(nullable=False)
    domestic_competition_id: Mapped[str | None] = mapped_column(nullable=True)
    total_market_value_eur: Mapped[int | None] = mapped_column(nullable=True)
    squad_size: Mapped[int | None] = mapped_column(nullable=True)
    average_age: Mapped[Decimal | None] = mapped_column(Numeric(4, 1), nullable=True)
    stadium_seats: Mapped[int | None] = mapped_column(nullable=True)
    stadium_name: Mapped[str | None] = mapped_column(nullable=True)
    coach_name: Mapped[str | None] = mapped_column(nullable=True)
    url: Mapped[str] = mapped_column(nullable=False)


class RealNationalTeamSchema(Base):
    """National-team reference data (source: Transfermarkt national-team export).

    `fifa_ranking` is the real/current FIFA ranking, distinct from the
    static/synthetic `TeamSchema.fifa_ranking_pre_tournament`.
    """

    __tablename__ = "real_national_team"

    national_team_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(nullable=False)
    country_name: Mapped[str] = mapped_column(nullable=False)
    confederation: Mapped[str] = mapped_column(nullable=False)
    fifa_ranking: Mapped[int | None] = mapped_column(nullable=True)
    squad_size: Mapped[int | None] = mapped_column(nullable=True)
    average_age: Mapped[Decimal | None] = mapped_column(Numeric(4, 1), nullable=True)
    total_market_value_eur: Mapped[int | None] = mapped_column(nullable=True)
    coach_name: Mapped[str | None] = mapped_column(nullable=True)
    url: Mapped[str] = mapped_column(nullable=False)
