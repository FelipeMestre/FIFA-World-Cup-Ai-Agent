import datetime as dt

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from src.infra.postgres.schemas.base import Base


class MatchSchema(Base):
    __tablename__ = "match"

    # NOTE: the column is named `date`, same as the `datetime.date` type used
    # below -- imported as `dt.date` (module-qualified) rather than `date` so
    # this attribute doesn't shadow the type when SQLAlchemy resolves the
    # `Mapped[...]` annotation via `get_type_hints` after the class body runs.
    match_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    date: Mapped[dt.date] = mapped_column(nullable=False)
    kickoff_time_utc: Mapped[dt.time] = mapped_column(nullable=False)
    stage_id: Mapped[int] = mapped_column(ForeignKey("tournament_stage.stage_id"), nullable=False)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venue.venue_id"), nullable=False)
    home_team_id: Mapped[int] = mapped_column(ForeignKey("team.team_id"), nullable=False)
    away_team_id: Mapped[int] = mapped_column(ForeignKey("team.team_id"), nullable=False)
    home_score: Mapped[int] = mapped_column(nullable=False)
    away_score: Mapped[int] = mapped_column(nullable=False)
    # Legitimately null for matches not decided by a penalty shootout.
    home_penalty_score: Mapped[int | None] = mapped_column(nullable=True)
    away_penalty_score: Mapped[int | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(nullable=False)
    result_type: Mapped[str] = mapped_column(nullable=False)
    home_xg: Mapped[float] = mapped_column(nullable=False)
    away_xg: Mapped[float] = mapped_column(nullable=False)
    referee_id: Mapped[int] = mapped_column(ForeignKey("referee.referee_id"), nullable=False)
    player_of_the_match_id: Mapped[int] = mapped_column(
        ForeignKey("player.player_id"), nullable=False
    )


class MatchEventSchema(Base):
    __tablename__ = "match_event"

    event_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    match_id: Mapped[int] = mapped_column(ForeignKey("match.match_id"), nullable=False)
    minute: Mapped[int] = mapped_column(nullable=False)
    event_type: Mapped[str] = mapped_column(nullable=False)
    team_id: Mapped[int] = mapped_column(ForeignKey("team.team_id"), nullable=False)
    player_id: Mapped[int] = mapped_column(ForeignKey("player.player_id"), nullable=False)


class MatchTeamStatSchema(Base):
    __tablename__ = "match_team_stat"

    match_id: Mapped[int] = mapped_column(
        ForeignKey("match.match_id"), primary_key=True, autoincrement=False
    )
    team_id: Mapped[int] = mapped_column(
        ForeignKey("team.team_id"), primary_key=True, autoincrement=False
    )
    possession_pct: Mapped[int] = mapped_column(nullable=False)
    total_shots: Mapped[int] = mapped_column(nullable=False)
    shots_on_target: Mapped[int] = mapped_column(nullable=False)
    corners: Mapped[int] = mapped_column(nullable=False)
    fouls: Mapped[int] = mapped_column(nullable=False)
    offsides: Mapped[int] = mapped_column(nullable=False)
    saves: Mapped[int] = mapped_column(nullable=False)
    player_of_the_match: Mapped[str | None] = mapped_column(nullable=True)
    data_source: Mapped[str] = mapped_column(nullable=False)
    last_updated: Mapped[dt.date] = mapped_column(nullable=False)


class MatchLineupSchema(Base):
    __tablename__ = "match_lineup"

    lineup_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    match_id: Mapped[int] = mapped_column(ForeignKey("match.match_id"), nullable=False)
    player_id: Mapped[int] = mapped_column(ForeignKey("player.player_id"), nullable=False)
    team_id: Mapped[int] = mapped_column(ForeignKey("team.team_id"), nullable=False)
    is_starting_xi: Mapped[bool] = mapped_column(nullable=False)
    tactical_position: Mapped[str] = mapped_column(nullable=False)
    minutes_played: Mapped[int] = mapped_column(nullable=False)
