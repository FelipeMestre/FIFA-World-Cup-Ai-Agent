"""Pure-Transfermarkt-space match data: lineups, match events, and club-game
results. Every id here lives entirely in Transfermarkt's own id space -- none
of these tables FK to the synthetic `player`/`match`/`team` tables.
"""

from datetime import date

from sqlalchemy import Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from src.infra.postgres.schemas.base import Base


class RealGameLineupSchema(Base):
    """Per-game starting/bench lineup entry (source: Transfermarkt game_lineups.csv)."""

    __tablename__ = "real_game_lineup"

    game_lineups_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    real_game_id: Mapped[int] = mapped_column(nullable=False, index=True)
    real_player_id: Mapped[int] = mapped_column(
        ForeignKey("real_player.player_id"), nullable=False, index=True
    )
    real_club_id: Mapped[int] = mapped_column(
        ForeignKey("real_club.club_id"), nullable=False, index=True
    )
    lineup_type: Mapped[str] = mapped_column(nullable=False)
    position: Mapped[str | None] = mapped_column(nullable=True)
    squad_number: Mapped[int | None] = mapped_column(nullable=True)
    is_captain: Mapped[bool] = mapped_column(Boolean, nullable=False)
    lineup_date: Mapped[date | None] = mapped_column(nullable=True)


class RealMatchEventSchema(Base):
    """In-game event: goal, card, substitution, etc. (source: Transfermarkt game_events.csv)."""

    __tablename__ = "real_match_event"

    game_event_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    real_game_id: Mapped[int] = mapped_column(nullable=False, index=True)
    minute: Mapped[int | None] = mapped_column(nullable=True)
    event_type: Mapped[str] = mapped_column(nullable=False)
    real_club_id: Mapped[int | None] = mapped_column(
        ForeignKey("real_club.club_id"), nullable=True, index=True
    )
    club_name_at_time: Mapped[str | None] = mapped_column(nullable=True)
    real_player_id: Mapped[int | None] = mapped_column(
        ForeignKey("real_player.player_id"), nullable=True, index=True
    )
    description: Mapped[str | None] = mapped_column(nullable=True)
    player_in_id: Mapped[int | None] = mapped_column(
        ForeignKey("real_player.player_id"), nullable=True
    )
    assist_player_id: Mapped[int | None] = mapped_column(
        ForeignKey("real_player.player_id"), nullable=True
    )
    event_date: Mapped[date | None] = mapped_column(nullable=True)


class RealClubGameSchema(Base):
    """Per-club view of a single game result (source: Transfermarkt club_games.csv).

    Composite PK mirrors `MatchTeamStatSchema`'s per-team-per-match shape.
    """

    __tablename__ = "real_club_game"

    real_game_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    real_club_id: Mapped[int] = mapped_column(ForeignKey("real_club.club_id"), primary_key=True)
    own_goals: Mapped[int | None] = mapped_column(nullable=True)
    own_position: Mapped[str | None] = mapped_column(nullable=True)
    own_manager_name: Mapped[str | None] = mapped_column(nullable=True)
    opponent_club_id: Mapped[int | None] = mapped_column(
        ForeignKey("real_club.club_id"), nullable=True, index=True
    )
    opponent_goals: Mapped[int | None] = mapped_column(nullable=True)
    opponent_position: Mapped[str | None] = mapped_column(nullable=True)
    opponent_manager_name: Mapped[str | None] = mapped_column(nullable=True)
    is_home: Mapped[bool | None] = mapped_column(nullable=True)
    is_win: Mapped[bool | None] = mapped_column(nullable=True)
