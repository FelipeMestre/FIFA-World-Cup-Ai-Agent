from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.teams.model.team import Team
from src.infra.postgres.config import get_db
from src.infra.postgres.interfaces.team_repository_interface import TeamRepositoryInterface
from src.infra.postgres.schemas.team_schema import TeamSchema


def _to_domain(row: TeamSchema) -> Team:
    return Team(
        id=row.team_id,
        name=row.team_name,
        fifa_code=row.fifa_code,
        group_letter=row.group_letter,
        confederation=row.confederation,
        fifa_ranking_pre_tournament=row.fifa_ranking_pre_tournament,
        elo_rating=row.elo_rating,
        manager_name=row.manager_name,
    )


class _SqlAlchemyTeamRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, team_id: int) -> Team | None:
        row = await self._session.get(TeamSchema, team_id)
        return _to_domain(row) if row else None

    async def list(self, limit: int = 100, offset: int = 0) -> list[Team]:
        result = await self._session.execute(
            select(TeamSchema).order_by(TeamSchema.team_id).limit(limit).offset(offset)
        )
        return [_to_domain(row) for row in result.scalars().all()]


def get_team_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TeamRepositoryInterface:
    return _SqlAlchemyTeamRepository(session)
