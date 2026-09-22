"""SQL-first aggregation for the `get_match_analysis` chat tool.

Mirrors `team_analytics_repository.py`'s structure: team resolution reuses
the same exact-then-fuzzy `ilike` approach (`_resolve_team`), applied to
both `home_team_query` and `away_team_query`. A match is looked up by the
resolved team-id pair in *either* home/away orientation (the user's stated
home/away may not match the recorded fixture), then narrowed by the optional
`stage`/`date` args when the same two teams played more than once.

Pure shape-building (stats split, timeline, lineups, ...) lives in
`_match_analytics_builders.py` to keep this file under the project's
400-line-per-file limit; this module is the SQL-fetching + orchestration
half only.
"""

import datetime as dt
from typing import Annotated

from fastapi import Depends
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.match_analytics.model.match_analysis import (
    MatchAnalysis,
    MatchAnalysisAmbiguous,
    MatchCandidate,
    PlayerOfMatch,
    TeamRef,
)
from src.infra.postgres.config import get_db
from src.infra.postgres.interfaces.match_analytics_repository_interface import (
    MatchAnalyticsRepositoryInterface,
)
from src.infra.postgres.repositories import _match_analytics_builders as builders
from src.infra.postgres.schemas.match_schema import (
    MatchEventSchema,
    MatchLineupSchema,
    MatchSchema,
    MatchTeamStatSchema,
)
from src.infra.postgres.schemas.national_team_schema import NationalTeamSchema
from src.infra.postgres.schemas.player_schema import PlayerSchema
from src.infra.postgres.schemas.reference_schema import TournamentStageSchema, VenueSchema

_ASSIST_EVENT_TYPE = "Assist"


class _SqlAlchemyMatchAnalyticsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_match_analysis(
        self,
        home_team_query: str,
        away_team_query: str,
        stage: str | None = None,
        date: str | None = None,
    ) -> MatchAnalysis | MatchAnalysisAmbiguous | None:
        home_team = await self._resolve_team(home_team_query)
        away_team = await self._resolve_team(away_team_query)
        if home_team is None or away_team is None:
            return None

        match_rows = await self._find_matches(home_team.team_id, away_team.team_id, stage, date)
        if not match_rows:
            return None

        if len(match_rows) > 1:
            return await self._build_ambiguous(match_rows)

        match, stage_name = match_rows[0]
        return await self._build_match_analysis(match, stage_name, home_team, away_team)

    async def _resolve_team(self, team_query: str) -> NationalTeamSchema | None:
        exact_stmt = select(NationalTeamSchema).where(
            or_(
                NationalTeamSchema.team_name.ilike(team_query),
                NationalTeamSchema.fifa_code.ilike(team_query),
            )
        )
        exact_match = (await self._session.execute(exact_stmt)).scalars().first()
        if exact_match is not None:
            return exact_match

        fuzzy_stmt = (
            select(NationalTeamSchema)
            .where(NationalTeamSchema.team_name.ilike(f"%{team_query}%"))
            .limit(1)
        )
        return (await self._session.execute(fuzzy_stmt)).scalars().first()

    async def _find_matches(
        self, home_id: int, away_id: int, stage: str | None, date: str | None
    ) -> list[tuple[MatchSchema, str]]:
        team_pair = or_(
            (MatchSchema.home_team_id == home_id) & (MatchSchema.away_team_id == away_id),
            (MatchSchema.home_team_id == away_id) & (MatchSchema.away_team_id == home_id),
        )
        stmt = (
            select(MatchSchema, TournamentStageSchema.stage_name)
            .join(TournamentStageSchema, TournamentStageSchema.stage_id == MatchSchema.stage_id)
            .where(team_pair)
            .order_by(MatchSchema.date)
        )
        if stage:
            stmt = stmt.where(TournamentStageSchema.stage_name.ilike(f"%{stage}%"))
        if date:
            stmt = stmt.where(MatchSchema.date == dt.date.fromisoformat(date))

        result = await self._session.execute(stmt)
        return [(row.MatchSchema, row.stage_name) for row in result.all()]

    async def _build_ambiguous(
        self, match_rows: list[tuple[MatchSchema, str]]
    ) -> MatchAnalysisAmbiguous:
        team_ids = {m.home_team_id for m, _ in match_rows} | {m.away_team_id for m, _ in match_rows}
        team_codes = await self._get_team_codes(team_ids)
        candidates = [
            MatchCandidate(
                id=str(match.match_id),
                stage_label=stage_name,
                date_label=match.date.strftime("%b %-d, %Y"),
                home_team_code=team_codes.get(match.home_team_id, "???"),
                away_team_code=team_codes.get(match.away_team_id, "???"),
                score=f"{match.home_score}–{match.away_score}",
            )
            for match, stage_name in match_rows
        ]
        return MatchAnalysisAmbiguous(candidates=candidates)

    async def _build_match_analysis(
        self,
        match: MatchSchema,
        stage_name: str,
        home_team: NationalTeamSchema,
        away_team: NationalTeamSchema,
    ) -> MatchAnalysis:
        # The recorded fixture, not the user's stated orientation, decides
        # which resolved team is actually home/away.
        home_team, away_team = (
            (home_team, away_team)
            if match.home_team_id == home_team.team_id
            else (away_team, home_team)
        )
        home_code = home_team.fifa_code or home_team.team_name[:3].upper()
        away_code = away_team.fifa_code or away_team.team_name[:3].upper()

        venue = await self._get_venue(match.venue_id)
        team_stats = await self._get_team_stats(match.match_id)
        events = await self._get_events(match.match_id)
        lineup_rows = await self._get_lineups(match.match_id)
        player_ids = {row.player_id for row in lineup_rows} | {e.player_id for e in events}
        player_names = await self._get_player_names(player_ids)

        team_codes = {home_team.team_id: home_code, away_team.team_id: away_code}
        goal_events = [e for e in events if e.event_type in ("Goal", "Own Goal")]
        assist_events = [e for e in events if e.event_type == _ASSIST_EVENT_TYPE]
        assists_by_key: dict[tuple[int, int], list[str]] = {}
        for assist in assist_events:
            key = (assist.minute, assist.team_id)
            assists_by_key.setdefault(key, []).append(player_names.get(assist.player_id, "Unknown"))

        potm_player = await self._get_player(match.player_of_the_match_id)
        potm_team_id = potm_player.team_id if potm_player else home_team.team_id
        potm_goal_count = sum(1 for e in goal_events if e.player_id == match.player_of_the_match_id)
        potm_team = home_team if potm_team_id == home_team.team_id else away_team
        potm_code = home_code if potm_team_id == home_team.team_id else away_code

        home_stat = team_stats.get(home_team.team_id, {})
        away_stat = team_stats.get(away_team.team_id, {})

        return MatchAnalysis(
            id=str(match.match_id),
            stage_label=stage_name,
            date_label=match.date.strftime("%b %-d, %Y"),
            venue_label=(f"{venue.stadium_name}, {venue.city}" if venue is not None else None),
            home_team=TeamRef(code=home_code, name=home_team.team_name),
            away_team=TeamRef(code=away_code, name=away_team.team_name),
            home_score=match.home_score,
            away_score=match.away_score,
            status_label=builders.build_status_label(
                match.status, match.home_penalty_score is not None
            ),
            home_scorers=builders.build_scorers_text(goal_events, home_team.team_id, player_names),
            away_scorers=builders.build_scorers_text(goal_events, away_team.team_id, player_names),
            stats=builders.build_stats(home_stat, away_stat),
            events=builders.build_events(goal_events, team_codes, player_names),
            player_of_match=(
                builders.build_player_of_match(
                    potm_player, potm_code, potm_team.team_name, potm_goal_count
                )
                if potm_player is not None
                else _unknown_player_of_match()
            ),
            timeline=builders.build_timeline(events, team_codes, player_names, assists_by_key),
            lineups=[
                builders.build_lineup(
                    home_code,
                    home_team.team_name,
                    [row for row in lineup_rows if row.team_id == home_team.team_id],
                    player_names,
                ),
                builders.build_lineup(
                    away_code,
                    away_team.team_name,
                    [row for row in lineup_rows if row.team_id == away_team.team_id],
                    player_names,
                ),
            ],
            footer_caption=builders.build_footer_caption(events),
        )

    async def _get_team_codes(self, team_ids: set[int]) -> dict[int, str]:
        if not team_ids:
            return {}
        stmt = select(NationalTeamSchema).where(NationalTeamSchema.team_id.in_(team_ids))
        result = await self._session.execute(stmt)
        return {
            row.team_id: row.fifa_code or row.team_name[:3].upper()
            for row in result.scalars().all()
        }

    async def _get_venue(self, venue_id: int) -> VenueSchema | None:
        stmt = select(VenueSchema).where(VenueSchema.venue_id == venue_id)
        return (await self._session.execute(stmt)).scalars().first()

    async def _get_team_stats(self, match_id: int) -> dict[int, dict[str, int]]:
        stmt = select(MatchTeamStatSchema).where(MatchTeamStatSchema.match_id == match_id)
        result = await self._session.execute(stmt)
        return {
            row.team_id: {
                "possession_pct": row.possession_pct,
                "total_shots": row.total_shots,
                "shots_on_target": row.shots_on_target,
                "corners": row.corners,
                "fouls": row.fouls,
                "offsides": row.offsides,
            }
            for row in result.scalars().all()
        }

    async def _get_events(self, match_id: int) -> list[MatchEventSchema]:
        stmt = (
            select(MatchEventSchema)
            .where(MatchEventSchema.match_id == match_id)
            .order_by(MatchEventSchema.minute)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def _get_lineups(self, match_id: int) -> list[MatchLineupSchema]:
        stmt = (
            select(MatchLineupSchema)
            .where(MatchLineupSchema.match_id == match_id)
            .order_by(MatchLineupSchema.lineup_id)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def _get_player_names(self, player_ids: set[int]) -> dict[int, str]:
        if not player_ids:
            return {}
        stmt = select(PlayerSchema).where(PlayerSchema.player_id.in_(player_ids))
        result = await self._session.execute(stmt)
        return {row.player_id: row.player_name for row in result.scalars().all()}

    async def _get_player(self, player_id: int) -> PlayerSchema | None:
        stmt = select(PlayerSchema).where(PlayerSchema.player_id == player_id)
        return (await self._session.execute(stmt)).scalars().first()


def _unknown_player_of_match() -> PlayerOfMatch:
    return PlayerOfMatch(name="Unknown", team_code="???", position="MID", note="")


def get_match_analytics_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> MatchAnalyticsRepositoryInterface:
    return _SqlAlchemyMatchAnalyticsRepository(session)
