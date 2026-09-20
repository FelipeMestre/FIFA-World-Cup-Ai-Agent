"""National-team reference data. Rows come from two independent sources:

- The synthetic WC2026 upload assigns `team_id` explicitly (its own id
  space) for every team competing in the tournament -- the WC2026-specific
  columns (`fifa_code`, `group_letter`, `fifa_ranking_pre_tournament`,
  `elo_rating`, `manager_name`) only ever come from here, and are nullable
  because a country that never qualified has none of these concepts.
- The Transfermarkt sync enriches a matching row (by name, via
  `RosterScopingService`) when one exists, or -- for a Transfermarkt
  country with no WC2026 match -- creates a new row itself, identified by
  `transfermarkt_id` (unique) instead of `team_id`. `team_id` is a Postgres
  IDENTITY column specifically so this insert path can omit it and let the
  database assign the next id atomically; computing "MAX(team_id) + 1" in
  application code would race under concurrent syncs (arq allows more than
  one running job at a time).

`fifa_ranking_pre_tournament` and `manager_name` are deliberately the only
ranking/coach fields kept -- Transfermarkt's own `fifa_ranking`/`coach_name`
are not migrated, since this dataset's own synthetic values are the ones
the product uses, for every row regardless of which sync created it.
"""

from decimal import Decimal

from sqlalchemy import Identity, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from src.infra.postgres.schemas.base import Base


class NationalTeamSchema(Base):
    __tablename__ = "national_team"

    team_id: Mapped[int] = mapped_column(Identity(always=False), primary_key=True)
    team_name: Mapped[str] = mapped_column(nullable=False)
    confederation: Mapped[str] = mapped_column(nullable=False)
    # WC2026-only -- null for a row Transfermarkt created for a country
    # that never qualified for the tournament.
    fifa_code: Mapped[str | None] = mapped_column(nullable=True)
    group_letter: Mapped[str | None] = mapped_column(nullable=True)
    fifa_ranking_pre_tournament: Mapped[int | None] = mapped_column(nullable=True)
    elo_rating: Mapped[int | None] = mapped_column(nullable=True)
    manager_name: Mapped[str | None] = mapped_column(nullable=True)
    # Transfermarkt enrichment -- nullable until a sync matches/creates this row.
    transfermarkt_id: Mapped[int | None] = mapped_column(nullable=True, unique=True)
    squad_size: Mapped[int | None] = mapped_column(nullable=True)
    average_age: Mapped[Decimal | None] = mapped_column(Numeric(4, 1), nullable=True)
    total_market_value_eur: Mapped[int | None] = mapped_column(nullable=True)
    url: Mapped[str | None] = mapped_column(nullable=True)
