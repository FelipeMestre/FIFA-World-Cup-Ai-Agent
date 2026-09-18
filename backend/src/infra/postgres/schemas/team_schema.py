from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from src.infra.postgres.schemas.base import Base


class TeamSchema(Base):
    __tablename__ = "team"

    team_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    team_name: Mapped[str] = mapped_column(nullable=False)
    fifa_code: Mapped[str] = mapped_column(nullable=False)
    group_letter: Mapped[str] = mapped_column(nullable=False)
    confederation: Mapped[str] = mapped_column(nullable=False)
    fifa_ranking_pre_tournament: Mapped[int] = mapped_column(nullable=False)
    elo_rating: Mapped[int] = mapped_column(nullable=False)
    manager_name: Mapped[str] = mapped_column(nullable=False)
    real_national_team_id: Mapped[int | None] = mapped_column(
        ForeignKey("real_national_team.national_team_id"), nullable=True
    )
