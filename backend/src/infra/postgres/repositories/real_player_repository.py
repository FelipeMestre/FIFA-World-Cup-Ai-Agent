"""Read-side repository for `real_player`. `search` backs the admin
"correct match" flow: given a doubtful `player_identity_link`, the admin
looks up the actual intended Transfermarkt player by name.
"""

from typing import Annotated, Any

from fastapi import Depends
from sqlalchemy import func, select
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
        # Two-tier, mirroring `_SqlAlchemyPlayerAnalyticsRepository._resolve_player`:
        # an exact (diacritic-insensitive) match first, falling back to a
        # substring match only when nothing matched exactly. `unaccent()` on
        # both sides makes an accented query (e.g. "Mbappé") resolve the
        # DB's unaccented "Mbappe" row -- requires the `unaccent` Postgres
        # extension, see migrations/versions. The substring tier still
        # benefits from the pg_trgm GIN index on the stored `full_name`
        # column (migration a1a2adf5c8b4), since `unaccent()` wrapping a
        # column reference doesn't stop the trigram index from being used
        # the way an expression index mismatch would.
        stripped = query.strip()
        exact_stmt = (
            select(RealPlayerSchema)
            .where(func.unaccent(RealPlayerSchema.full_name).ilike(func.unaccent(stripped)))
            .order_by(RealPlayerSchema.last_name, RealPlayerSchema.first_name)
            .limit(limit)
            .offset(offset)
        )
        exact_rows = (await self._session.execute(exact_stmt)).scalars().all()
        if exact_rows:
            return [_to_domain(row) for row in exact_rows]

        fuzzy_stmt = (
            select(RealPlayerSchema)
            .where(func.unaccent(RealPlayerSchema.full_name).ilike(func.unaccent(f"%{stripped}%")))
            .order_by(RealPlayerSchema.last_name, RealPlayerSchema.first_name)
            .limit(limit)
            .offset(offset)
        )
        fuzzy_rows = (await self._session.execute(fuzzy_stmt)).scalars().all()
        return [_to_domain(row) for row in fuzzy_rows]

    async def list_match_candidates(self) -> list[dict[str, Any]]:
        # Column-projected select, not a full-row fetch: the identity-link
        # rematch feature loads every real_player row (Transfermarkt-scale,
        # tens of thousands), and PlayerIdentityMatchingService.match() only
        # ever reads these five keys.
        result = await self._session.execute(
            select(
                RealPlayerSchema.player_id,
                RealPlayerSchema.first_name,
                RealPlayerSchema.last_name,
                RealPlayerSchema.date_of_birth,
                RealPlayerSchema.height_cm,
                RealPlayerSchema.current_national_team_id,
            )
        )
        return [
            {
                "player_id": row.player_id,
                "first_name": row.first_name,
                "last_name": row.last_name,
                "date_of_birth": row.date_of_birth,
                # Renamed from the persisted `height_cm` column -- the
                # matching service reads `height_in_cm` exactly (see its own
                # docstring on this exact class of bug).
                "height_in_cm": row.height_cm,
                "current_national_team_id": row.current_national_team_id,
            }
            for row in result.all()
        ]


def build_real_player_repository(session: AsyncSession) -> RealPlayerRepositoryInterface:
    return _SqlAlchemyRealPlayerRepository(session)


def get_real_player_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RealPlayerRepositoryInterface:
    return build_real_player_repository(session)
