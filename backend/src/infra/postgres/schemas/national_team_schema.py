"""National-team reference data: base rows come from the synthetic WC2026
dataset (`team_id` is that dataset's own id, still not autoincrement -- the
synthetic CSV upload assigns it), enriched in place by the Transfermarkt
sync via `real_national_team_id` and the columns below it. Transfermarkt
never creates a row here, only updates one matched by name against an
existing `team_id` row (see `TransfermarktSyncService`'s national_teams
step) -- so every row's WC2026-specific columns (`fifa_code`,
`group_letter`, `fifa_ranking_pre_tournament`, `elo_rating`,
`manager_name`) are always populated, while the Transfermarkt-sourced
columns are nullable until (if ever) a sync enriches that row.

`fifa_ranking_pre_tournament` and `manager_name` are deliberately the only
ranking/coach fields kept -- Transfermarkt's own `fifa_ranking`/`coach_name`
are not migrated, since this dataset's own synthetic values are the ones
the product uses.
"""

from decimal import Decimal

from sqlalchemy import Numeric
from sqlalchemy.orm import Mapped, mapped_column

from src.infra.postgres.schemas.base import Base


class NationalTeamSchema(Base):
    __tablename__ = "national_team"

    team_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    team_name: Mapped[str] = mapped_column(nullable=False)
    fifa_code: Mapped[str] = mapped_column(nullable=False)
    group_letter: Mapped[str] = mapped_column(nullable=False)
    confederation: Mapped[str] = mapped_column(nullable=False)
    fifa_ranking_pre_tournament: Mapped[int] = mapped_column(nullable=False)
    elo_rating: Mapped[int] = mapped_column(nullable=False)
    manager_name: Mapped[str] = mapped_column(nullable=False)
    # Transfermarkt enrichment -- nullable until a sync matches this row.
    real_national_team_id: Mapped[int | None] = mapped_column(nullable=True, unique=True)
    squad_size: Mapped[int | None] = mapped_column(nullable=True)
    average_age: Mapped[Decimal | None] = mapped_column(Numeric(4, 1), nullable=True)
    total_market_value_eur: Mapped[int | None] = mapped_column(nullable=True)
    url: Mapped[str | None] = mapped_column(nullable=True)
