from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.players.model.player import Player
from src.infra.postgres.config import get_db
from src.infra.postgres.interfaces.player_repository_interface import PlayerRepositoryInterface
from src.infra.postgres.schemas.player_schema import PlayerSchema


def _to_domain(row: PlayerSchema) -> Player:
    return Player(
        id=row.player_id,
        team_id=row.team_id,
        name=row.player_name,
        position=row.position,
        club_team=row.club_team,
        market_value_eur=row.market_value_eur,
        caps=row.caps,
        date_of_birth=row.date_of_birth,
        height_cm=row.height_cm,
        goals=row.goals,
    )


class _SqlAlchemyPlayerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, player_id: int) -> Player | None:
        row = await self._session.get(PlayerSchema, player_id)
        return _to_domain(row) if row else None

    async def list(self, limit: int = 100, offset: int = 0) -> list[Player]:
        result = await self._session.execute(
            select(PlayerSchema).order_by(PlayerSchema.player_id).limit(limit).offset(offset)
        )
        return [_to_domain(row) for row in result.scalars().all()]


def get_player_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PlayerRepositoryInterface:
    return _SqlAlchemyPlayerRepository(session)
