from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.national_teams.model.national_team import NationalTeam
from src.infra.postgres.config import get_db
from src.infra.postgres.interfaces.national_team_repository_interface import (
    NationalTeamRepositoryInterface,
)
from src.infra.postgres.schemas.national_team_schema import NationalTeamSchema


def _to_domain(row: NationalTeamSchema) -> NationalTeam:
    return NationalTeam(
        id=row.team_id,
        name=row.team_name,
        fifa_code=row.fifa_code,
        group_letter=row.group_letter,
        confederation=row.confederation,
        fifa_ranking_pre_tournament=row.fifa_ranking_pre_tournament,
        elo_rating=row.elo_rating,
        manager_name=row.manager_name,
        real_national_team_id=row.real_national_team_id,
        squad_size=row.squad_size,
        average_age=row.average_age,
        total_market_value_eur=row.total_market_value_eur,
        url=row.url,
    )


class _SqlAlchemyNationalTeamRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, team_id: int) -> NationalTeam | None:
        row = await self._session.get(NationalTeamSchema, team_id)
        return _to_domain(row) if row else None

    async def list(self, limit: int = 100, offset: int = 0) -> list[NationalTeam]:
        result = await self._session.execute(
            select(NationalTeamSchema)
            .order_by(NationalTeamSchema.team_id)
            .limit(limit)
            .offset(offset)
        )
        return [_to_domain(row) for row in result.scalars().all()]


def get_national_team_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> NationalTeamRepositoryInterface:
    return _SqlAlchemyNationalTeamRepository(session)
