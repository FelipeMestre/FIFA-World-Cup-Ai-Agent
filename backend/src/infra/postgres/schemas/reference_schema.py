"""Small reference/catalog tables shared by the matches bounded context.

These are not owned by any single bounded context's API (no dedicated router
in this phase) but are referenced by `match` via foreign keys.
"""

from sqlalchemy.orm import Mapped, mapped_column

from src.infra.postgres.schemas.base import Base


class VenueSchema(Base):
    __tablename__ = "venue"

    venue_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    stadium_name: Mapped[str] = mapped_column(nullable=False)
    city: Mapped[str] = mapped_column(nullable=False)
    country: Mapped[str] = mapped_column(nullable=False)
    capacity: Mapped[int] = mapped_column(nullable=False)
    latitude: Mapped[float] = mapped_column(nullable=False)
    longitude: Mapped[float] = mapped_column(nullable=False)
    elevation_meters: Mapped[int] = mapped_column(nullable=False)


class TournamentStageSchema(Base):
    __tablename__ = "tournament_stage"

    stage_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    stage_name: Mapped[str] = mapped_column(nullable=False)
    is_knockout: Mapped[bool] = mapped_column(nullable=False)


class RefereeSchema(Base):
    __tablename__ = "referee"

    referee_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(nullable=False)
    country: Mapped[str] = mapped_column(nullable=False)
    avg_cards_per_game: Mapped[float] = mapped_column(nullable=False)
