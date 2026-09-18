from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.matches.model.match import Match
from src.infra.postgres.config import get_db
from src.infra.postgres.interfaces.match_repository_interface import MatchRepositoryInterface
from src.infra.postgres.schemas.match_schema import MatchSchema


def _to_domain(row: MatchSchema) -> Match:
    return Match(
        id=row.match_id,
        date=row.date,
        kickoff_time_utc=row.kickoff_time_utc,
        stage_id=row.stage_id,
        venue_id=row.venue_id,
        home_team_id=row.home_team_id,
        away_team_id=row.away_team_id,
        home_score=row.home_score,
        away_score=row.away_score,
        home_penalty_score=row.home_penalty_score,
        away_penalty_score=row.away_penalty_score,
        status=row.status,
        result_type=row.result_type,
        home_xg=row.home_xg,
        away_xg=row.away_xg,
        referee_id=row.referee_id,
        player_of_the_match_id=row.player_of_the_match_id,
    )


class _SqlAlchemyMatchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, match_id: int) -> Match | None:
        row = await self._session.get(MatchSchema, match_id)
        return _to_domain(row) if row else None

    async def list(self, limit: int = 100, offset: int = 0) -> list[Match]:
        result = await self._session.execute(
            select(MatchSchema).order_by(MatchSchema.match_id).limit(limit).offset(offset)
        )
        return [_to_domain(row) for row in result.scalars().all()]


def get_match_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MatchRepositoryInterface:
    return _SqlAlchemyMatchRepository(session)
