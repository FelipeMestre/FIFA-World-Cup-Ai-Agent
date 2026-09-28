from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from src.domain.matches.model.match import Match, MatchSearchRow
from src.infra.postgres.config import get_db
from src.infra.postgres.interfaces.match_repository_interface import MatchRepositoryInterface
from src.infra.postgres.schemas.match_schema import MatchSchema
from src.infra.postgres.schemas.national_team_schema import NationalTeamSchema


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

    async def search(self, query: str) -> list[MatchSearchRow]:
        """Matches where either the home or away team's name/FIFA code
        contains `query` (case/diacritic-insensitive). No `limit`/`offset` --
        an explicit product decision (see `odd/tasks/match-selector.md`):
        the whole tournament is ~100 matches, so a filtered result set is
        always small.
        """
        home_team = aliased(NationalTeamSchema)
        away_team = aliased(NationalTeamSchema)
        pattern = f"%{query}%"

        stmt = (
            select(MatchSchema, home_team.team_name, away_team.team_name)
            .join(home_team, home_team.team_id == MatchSchema.home_team_id)
            .join(away_team, away_team.team_id == MatchSchema.away_team_id)
            .where(
                or_(
                    func.unaccent(home_team.team_name).ilike(func.unaccent(pattern)),
                    func.unaccent(home_team.fifa_code).ilike(func.unaccent(pattern)),
                    func.unaccent(away_team.team_name).ilike(func.unaccent(pattern)),
                    func.unaccent(away_team.fifa_code).ilike(func.unaccent(pattern)),
                )
            )
            .order_by(MatchSchema.date.asc())
        )
        result = await self._session.execute(stmt)
        return [
            MatchSearchRow(
                match=_to_domain(row), home_team_name=home_name, away_team_name=away_name
            )
            for row, home_name, away_name in result.all()
        ]


def get_match_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MatchRepositoryInterface:
    return _SqlAlchemyMatchRepository(session)
