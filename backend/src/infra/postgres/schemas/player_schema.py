from datetime import date

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from src.infra.postgres.schemas.base import Base


class PlayerSchema(Base):
    """Squad roster (source: squads_and_players.csv)."""

    __tablename__ = "player"

    player_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    team_id: Mapped[int] = mapped_column(ForeignKey("national_team.team_id"), nullable=False)
    player_name: Mapped[str] = mapped_column(nullable=False)
    position: Mapped[str] = mapped_column(nullable=False)
    club_team: Mapped[str] = mapped_column(nullable=False)
    market_value_eur: Mapped[int] = mapped_column(nullable=False)
    caps: Mapped[int] = mapped_column(nullable=False)
    date_of_birth: Mapped[date] = mapped_column(nullable=False)
    height_cm: Mapped[int] = mapped_column(nullable=False)
    goals: Mapped[int] = mapped_column(nullable=False)


class PlayerStatSchema(Base):
    """Aggregate per-player tournament statistics (source: player_stats.csv).

    Known data-quality gap in the source dataset, encoded here as nullable
    rather than "fixed": `shots`, `shots_on_target`, and `average_rating` are
    always null upstream. `clean_sheets`/`saves`/`goals_conceded` are only
    populated for goalkeepers.
    """

    __tablename__ = "player_stat"

    player_id: Mapped[int] = mapped_column(
        ForeignKey("player.player_id"), primary_key=True, autoincrement=False
    )
    player_name: Mapped[str] = mapped_column(nullable=False)
    team_id: Mapped[int] = mapped_column(ForeignKey("national_team.team_id"), nullable=False)
    position: Mapped[str] = mapped_column(nullable=False)
    matches_played: Mapped[int] = mapped_column(nullable=False)
    matches_started: Mapped[int] = mapped_column(nullable=False)
    minutes_played: Mapped[int] = mapped_column(nullable=False)
    goals: Mapped[int] = mapped_column(nullable=False)
    assists: Mapped[int] = mapped_column(nullable=False)
    shots: Mapped[int | None] = mapped_column(nullable=True)
    shots_on_target: Mapped[int | None] = mapped_column(nullable=True)
    yellow_cards: Mapped[int] = mapped_column(nullable=False)
    red_cards: Mapped[int] = mapped_column(nullable=False)
    penalty_goals: Mapped[int] = mapped_column(nullable=False)
    own_goals: Mapped[int] = mapped_column(nullable=False)
    clean_sheets: Mapped[int | None] = mapped_column(nullable=True)
    saves: Mapped[int | None] = mapped_column(nullable=True)
    goals_conceded: Mapped[int | None] = mapped_column(nullable=True)
    average_rating: Mapped[float | None] = mapped_column(nullable=True)
    data_source: Mapped[str | None] = mapped_column(nullable=True)
    last_verified: Mapped[date] = mapped_column(nullable=False)
