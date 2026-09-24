"""Read-side repository for `real_player`. `search` backs the admin
"correct match" flow: given a doubtful `player_identity_link`, the admin
looks up the actual intended Transfermarkt player by name.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.ingestion.model.real_player import RealPlayer
from src.infra.postgres.config import get_db
from src.infra.postgres.interfaces.real_player_repository_interface import (
    RealPlayerRepositoryInterface,
)
from src.infra.postgres.schemas.real_player_schema import RealPlayerSchema


def _to_domain(row: RealPlayerSchema) -> RealPlayer:
    return RealPlayer(
        player_id=row.player_id,
        first_name=row.first_name,
        last_name=row.last_name,
        date_of_birth=row.date_of_birth,
        country_of_birth=row.country_of_birth,
        country_of_citizenship=row.country_of_citizenship,
        position=row.position,
        sub_position=row.sub_position,
        foot=row.foot,
        height_cm=row.height_cm,
        current_club_id=row.current_club_id,
        current_national_team_id=row.current_national_team_id,
        international_caps=row.international_caps,
        international_goals=row.international_goals,
        market_value_eur=row.market_value_eur,
        highest_market_value_eur=row.highest_market_value_eur,
        contract_expiration_date=row.contract_expiration_date,
        profile_url=row.profile_url,
        last_synced_at=row.last_synced_at,
    )


class _SqlAlchemyRealPlayerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, player_id: int) -> RealPlayer | None:
        row = await self._session.get(RealPlayerSchema, player_id)
        return _to_domain(row) if row else None

    async def search(self, query: str, limit: int = 20, offset: int = 0) -> list[RealPlayer]:
        # Matches the pg_trgm GIN index on the stored `full_name` column
        # (migration a1a2adf5c8b4) -- an ILIKE directly on that column, not
        # a query-time concatenation, is what makes the planner use it
        # instead of a sequential scan as the table grows to Transfermarkt's
        # full player count.
        pattern = f"%{query.strip()}%"
        result = await self._session.execute(
            select(RealPlayerSchema)
            .where(RealPlayerSchema.full_name.ilike(pattern))
            .order_by(RealPlayerSchema.last_name, RealPlayerSchema.first_name)
            .limit(limit)
            .offset(offset)
        )
        return [_to_domain(row) for row in result.scalars().all()]


def get_real_player_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RealPlayerRepositoryInterface:
    return _SqlAlchemyRealPlayerRepository(session)
