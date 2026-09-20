"""Transfermarkt club reference data.

Mirrors the Transfermarkt club export and is the target of `real_player`'s
`current_club_id` foreign key. National-team reference data lives on
`national_team` (`national_team_schema.py`) instead of a separate
`real_*` table -- see that module's docstring.
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
