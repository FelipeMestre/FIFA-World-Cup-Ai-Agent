"""SQL-first aggregation for the `get_player_analysis`,
`get_player_comparison`, and `query_player_stats` chat tools.

Pure position/per-90/percentile math lives in `_player_stat_helpers.py`;
single-player breakdown building lives in `_player_analysis_view.py`;
two-player comparison row/insight building lives in
`_player_comparison_view.py`; list/filter/sort SQL lives in
`_player_ranking_query.py`. This file keeps the public repository methods
and the DB-touching helpers (`_resolve_player`, `_get_player_stat`,
`_get_team_code`, `_get_position_peers`) analysis and comparison share.

Known data-quality gaps in the source dataset (see `PlayerStatSchema`'s own
docstring): `shots`/`shots_on_target`/`average_rating` are always null
upstream, and `clean_sheets`/`saves`/`goals_conceded` are only populated for
goalkeepers.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.chat.exceptions import chat_exceptions
from src.domain.player_analytics.model.player_analysis import PlayerAnalysis
from src.domain.player_analytics.model.player_comparison import PlayerComparison
from src.domain.player_analytics.model.player_ranking import PlayerRanking, QueryPlayerStatsRequest
from src.infra.postgres.config import get_db
from src.infra.postgres.interfaces.player_analytics_repository_interface import (
    PlayerAnalyticsRepositoryInterface,
)
from src.infra.postgres.interfaces.player_club_career_repository_interface import (
    PlayerClubCareerRepositoryInterface,
)
from src.infra.postgres.interfaces.real_player_repository_interface import (
    RealPlayerRepositoryInterface,
)
from src.infra.postgres.repositories import _player_analysis_view as analysis_view
from src.infra.postgres.repositories import _player_comparison_view as comparison_view
from src.infra.postgres.repositories import _player_ranking_query as ranking_query
from src.infra.postgres.repositories import _transfermarkt_player_view as fallback_view
from src.infra.postgres.repositories._player_stat_helpers import (
    Position,
    first_letter_for_position,
    normalize_position,
    player_initials,
)
from src.infra.postgres.repositories.player_club_career_repository import (
    build_player_club_career_repository,
)
from src.infra.postgres.repositories.real_player_repository import build_real_player_repository
from src.infra.postgres.schemas.national_team_schema import NationalTeamSchema
from src.infra.postgres.schemas.player_schema import PlayerSchema, PlayerStatSchema


class _SqlAlchemyPlayerAnalyticsRepository:
    def __init__(
        self,
        session: AsyncSession,
        club_career_repository: PlayerClubCareerRepositoryInterface | None = None,
        real_player_repository: RealPlayerRepositoryInterface | None = None,
    ) -> None:
        self._session = session
        self._club_career = club_career_repository or build_player_club_career_repository(session)
        self._real_player = real_player_repository or build_real_player_repository(session)

    async def get_player_analysis(self, player_query: str) -> PlayerAnalysis | None:
        player_row = await self._resolve_player(player_query)
        stat_row = None if player_row is None else await self._get_player_stat(player_row.player_id)
        if player_row is not None and stat_row is not None:
            return await self._build_world_cup_analysis(player_row, stat_row)

        # No World Cup `player` row at all, or a row with no `player_stat`
        # (never played, or a stats-collection gap) -- both fall back to the
        # Transfermarkt-sourced `real_player` table so the tool still
        # answers instead of reporting "not found".
        return await self._build_transfermarkt_fallback_analysis(player_query)

    async def _build_world_cup_analysis(
        self, player_row: PlayerSchema, stat_row: PlayerStatSchema
    ) -> PlayerAnalysis:
        position = normalize_position(stat_row.position or player_row.position)
        team_code = await self._get_team_code(player_row.team_id)
        peer_rows = await self._get_position_peers(position)
        club_career = await self._club_career.get_approved_career(player_row.player_id)

        is_gk = position == "GK"
        primary_percentile = analysis_view.primary_contribution_percentile(
            stat_row, peer_rows, is_gk
        )
        tier_label, tier_segments = analysis_view.tier_for_percentile(primary_percentile)

        return PlayerAnalysis(
            id=str(player_row.player_id),
            name=player_row.player_name,
            initials=player_initials(player_row.player_name),
            team_code=team_code,
            position=position,
            appearances=stat_row.matches_played,
            minutes=stat_row.minutes_played,
            scope_label=f"WC 2026 · {stat_row.matches_played} apps",
            tier_label=tier_label,
            tier_segments=tier_segments,
            discipline_label=analysis_view.discipline_label(stat_row),
            chips=analysis_view.build_chips(stat_row, is_gk),
            footer_caption=(
                f"{stat_row.matches_played} apps · {stat_row.minutes_played} min · "
                f"verified {stat_row.last_verified.isoformat()}"
            ),
            full_breakdown=analysis_view.build_full_breakdown(stat_row, peer_rows, is_gk),
            per_ninety_vs_position_average=analysis_view.build_benchmarks(
                stat_row, peer_rows, is_gk
            ),
            club_profile=None if club_career is None else club_career.profile,
            transfers=[] if club_career is None else list(club_career.transfers),
            career_seasons=[] if club_career is None else list(club_career.career_seasons),
        )

    async def _build_transfermarkt_fallback_analysis(
        self, player_query: str
    ) -> PlayerAnalysis | None:
        matches = await self._real_player.search(player_query, limit=1)
        if not matches:
            return None
        real_player = matches[0]

        career = await self._club_career.get_career_by_real_player_id(real_player.player_id)
        position = normalize_position(real_player.position)
        appearances = fallback_view.total_appearances(career.career_seasons)
        minutes = fallback_view.total_minutes(career.career_seasons)
        # Sentinels the frontend renders as a badge instead of plain text --
        # there's no national-team code to fall back on outside the World
        # Cup path, so a retired/clubless player needs an explicit state
        # rather than a bare "???".
        if career.profile.is_retired:
            team_code = "RETIRED"
        else:
            team_code = career.profile.current_club or "FREE"
        name = f"{real_player.first_name} {real_player.last_name}"

        return PlayerAnalysis(
            id=str(real_player.player_id),
            name=name,
            initials=player_initials(name),
            team_code=team_code,
            position=position,
            appearances=appearances,
            minutes=minutes,
            # No World Cup tournament scope or peer-ranked tier applies to a
            # club-career totals view -- neutral, non-tiering labels rather
            # than forcing WC-style percentile language onto data that has
            # no peer population (see task file's design decisions).
            scope_label="Club career · totals",
            tier_label="Club career",
            tier_segments=0,
            discipline_label=fallback_view.discipline_label(career.career_seasons),
            chips=fallback_view.build_chips(career.career_seasons),
            footer_caption=f"{appearances} apps · {minutes} min · club career totals",
            full_breakdown=fallback_view.build_full_breakdown(career.career_seasons),
            per_ninety_vs_position_average=[],
            club_profile=career.profile,
            transfers=list(career.transfers),
            career_seasons=list(career.career_seasons),
        )

    async def get_player_comparison(
        self, player_a_query: str, player_b_query: str
    ) -> PlayerComparison:
        player_a_row = await self._require_player(player_a_query)
        player_b_row = await self._require_player(player_b_query)
        if player_a_row.player_id == player_b_row.player_id:
            raise chat_exceptions.SamePlayerComparisonError(
                f"'{player_a_query}' and '{player_b_query}' both resolved to "
                f"{player_a_row.player_name} -- pick two different players to compare."
            )

        stat_a = await self._require_player_stat(player_a_row.player_id, player_a_query)
        stat_b = await self._require_player_stat(player_b_row.player_id, player_b_query)

        position_a = normalize_position(stat_a.position or player_a_row.position)
        position_b = normalize_position(stat_b.position or player_b_row.position)
        team_code_a = await self._get_team_code(player_a_row.team_id)
        team_code_b = await self._get_team_code(player_b_row.team_id)
        peers_a = await self._get_position_peers(position_a)
        peers_b = (
            peers_a if position_b == position_a else await self._get_position_peers(position_b)
        )

        rows = comparison_view.build_comparison_rows(stat_a, peers_a, stat_b, peers_b)

        return PlayerComparison(
            id=f"{player_a_row.player_id}-vs-{player_b_row.player_id}",
            normalization="per90",
            scope_label="WC 2026 · Per-90 comparison",
            player_a=comparison_view.build_comparison_player_ref(
                player_a_row, stat_a, position_a, team_code_a
            ),
            player_b=comparison_view.build_comparison_player_ref(
                player_b_row, stat_b, position_b, team_code_b
            ),
            rows=rows,
            insights=comparison_view.build_comparison_insights(
                player_a_row.player_name, player_b_row.player_name, rows
            ),
            min_minutes_caption=(
                "Percentiles ranked against same-position players with minutes played > 0."
            ),
        )

    async def query_player_stats(self, request: QueryPlayerStatsRequest) -> PlayerRanking:
        return await ranking_query.query_player_stats(self._session, request)

    async def _require_player(self, player_query: str) -> PlayerSchema:
        player_row = await self._resolve_player(player_query)
        if player_row is None:
            raise chat_exceptions.PlayerNotFoundError(f"No player found matching '{player_query}'.")
        return player_row

    async def _require_player_stat(self, player_id: int, player_query: str) -> PlayerStatSchema:
        stat_row = await self._get_player_stat(player_id)
        if stat_row is None:
            raise chat_exceptions.PlayerNotFoundError(f"No stats recorded for '{player_query}'.")
        return stat_row

    async def _resolve_player(self, player_query: str) -> PlayerSchema | None:
        # `unaccent()` on both sides makes matching diacritic-insensitive (e.g. a
        # "Mbappé" query resolves the DB's unaccented "Kylian Mbappe" row) --
        # requires the `unaccent` Postgres extension, see migrations/versions.
        exact_stmt = select(PlayerSchema).where(
            func.unaccent(PlayerSchema.player_name).ilike(func.unaccent(player_query))
        )
        exact_match = (await self._session.execute(exact_stmt)).scalars().first()
        if exact_match is not None:
            return exact_match

        fuzzy_stmt = (
            select(PlayerSchema)
            .where(
                func.unaccent(PlayerSchema.player_name).ilike(func.unaccent(f"%{player_query}%"))
            )
            .limit(1)
        )
        return (await self._session.execute(fuzzy_stmt)).scalars().first()

    async def _get_player_stat(self, player_id: int) -> PlayerStatSchema | None:
        return await self._session.get(PlayerStatSchema, player_id)

    async def _get_team_code(self, team_id: int) -> str:
        team_row = await self._session.get(NationalTeamSchema, team_id)
        if team_row is None:
            return "???"
        return team_row.fifa_code or team_row.team_name[:3].upper()

    async def _get_position_peers(self, position: Position) -> list[PlayerStatSchema]:
        # Filters by first letter in SQL rather than fetching every row and
        # re-running `normalize_position` in Python. Every real position
        # code in this schema starts with G/D/M/F, so this drops only
        # `normalize_position`'s garbage-input fallback (unrecognized
        # letter -> MID), which never fires on real data.
        letter = first_letter_for_position(position)
        stmt = select(PlayerStatSchema).where(
            PlayerStatSchema.minutes_played > 0,
            PlayerStatSchema.position.ilike(f"{letter}%"),
        )
        return (await self._session.execute(stmt)).scalars().all()


def get_player_analytics_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PlayerAnalyticsRepositoryInterface:
    return _SqlAlchemyPlayerAnalyticsRepository(session)
