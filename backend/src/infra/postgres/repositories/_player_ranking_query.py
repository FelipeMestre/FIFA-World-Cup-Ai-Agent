"""SQL for `query_player_stats`.

World Cup reads `player_stat`. Club seasons sum approved-link
`real_player_season_stat` rows for the requested season years and
competition. Filters and sort use the allowlisted field catalog. The two
datasets are never mixed.
"""

from typing import Any

from sqlalchemy import Select, and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.chat.exceptions.chat_exceptions import RankingQueryError
from src.domain.player_analytics.model.player_ranking import (
    GK_ONLY_FIELDS,
    NULLABLE_STAT_FIELDS,
    PER90_FIELDS,
    ROSTER_FIELDS,
    FilterOp,
    PlayerRanking,
    PlayerStatField,
    QueryDataset,
    QueryPlayerStatsRequest,
    SortDir,
    StatFilter,
    used_fields,
)
from src.infra.postgres.repositories._player_ranking_rows import _build_ranking
from src.infra.postgres.repositories._player_stat_field_expr import (
    age_years_expr,
    club_stat_aggregates,
    compare,
    nationality_match,
    position_match,
    season_start_year_expr,
    team_code_expr,
    world_cup_stat_expr,
)
from src.infra.postgres.schemas.national_team_schema import NationalTeamSchema
from src.infra.postgres.schemas.player_identity_link_schema import (
    LinkReviewStatus,
    PlayerIdentityLinkSchema,
)
from src.infra.postgres.schemas.player_schema import PlayerSchema, PlayerStatSchema
from src.infra.postgres.schemas.real_player_schema import RealPlayerSeasonStatSchema


def _numeric(value: str | int | float) -> float:
    if isinstance(value, bool):
        raise RankingQueryError("Filter value must be a number.")
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(str(value).strip())
    except ValueError as exc:
        raise RankingQueryError(f"Expected a number, got '{value}'.") from exc


def _roster_clause(item: StatFilter):
    if item.field == PlayerStatField.POSITION:
        if item.op != FilterOp.EQ:
            raise RankingQueryError("position only supports op=eq.")
        try:
            return position_match(str(item.value))
        except ValueError as exc:
            raise RankingQueryError(str(exc)) from exc
    if item.field == PlayerStatField.NATIONALITY:
        if item.op != FilterOp.EQ:
            raise RankingQueryError("nationality only supports op=eq.")
        return nationality_match(str(item.value))
    if item.field == PlayerStatField.AGE:
        return compare(age_years_expr(), item.op, _numeric(item.value))
    return compare(PlayerSchema.height_cm, item.op, _numeric(item.value))


def _stat_clause(expr, item: StatFilter):
    return compare(expr, item.op, _numeric(item.value))


def _nullable_base(field: PlayerStatField):
    stat = PlayerStatSchema
    if field in {PlayerStatField.SAVES, PlayerStatField.SAVES_PER90}:
        return stat.saves.is_not(None)
    if field == PlayerStatField.CLEAN_SHEETS:
        return stat.clean_sheets.is_not(None)
    if field in {PlayerStatField.GOALS_CONCEDED, PlayerStatField.GOALS_CONCEDED_PER90}:
        return stat.goals_conceded.is_not(None)
    return None


def _world_cup_base_filters(request: QueryPlayerStatsRequest) -> list:
    fields = used_fields(request.sort_by, request.filters)
    filters: list = []
    if fields & PER90_FIELDS:
        filters.append(PlayerStatSchema.minutes_played > 0)
    if fields & GK_ONLY_FIELDS:
        filters.append(PlayerSchema.position.ilike("G%"))
    for field in fields & NULLABLE_STAT_FIELDS:
        clause = _nullable_base(field)
        if clause is not None:
            filters.append(clause)
    for item in request.filters:
        if item.field in ROSTER_FIELDS:
            filters.append(_roster_clause(item))
        else:
            expr = world_cup_stat_expr(item.field)
            filters.append(_stat_clause(expr, item))
    return filters


def _sort_order(sort_expr, request: QueryPlayerStatsRequest, minutes_expr):
    primary = sort_expr.asc() if request.sort_dir == SortDir.ASC else desc(sort_expr)
    return primary.nulls_last(), desc(minutes_expr), PlayerSchema.player_id


async def query_world_cup(session: AsyncSession, request: QueryPlayerStatsRequest) -> PlayerRanking:
    sort_expr = world_cup_stat_expr(request.sort_by)
    if sort_expr is None:
        raise RankingQueryError(f"Cannot sort World Cup stats by '{request.sort_by}'.")
    labeled = sort_expr.label("sort_value")
    filters = _world_cup_base_filters(request)
    stmt = (
        select(
            PlayerSchema.player_id,
            PlayerSchema.player_name,
            PlayerSchema.position,
            PlayerSchema.club_team,
            PlayerSchema.height_cm,
            age_years_expr().label("age"),
            team_code_expr().label("team_code"),
            PlayerStatSchema.matches_played.label("appearances"),
            PlayerStatSchema.minutes_played.label("minutes"),
            PlayerStatSchema.goals,
            PlayerStatSchema.assists,
            PlayerStatSchema.yellow_cards,
            PlayerStatSchema.red_cards,
            PlayerStatSchema.matches_started.label("starts"),
            PlayerStatSchema.penalty_goals,
            PlayerStatSchema.saves,
            PlayerStatSchema.clean_sheets,
            PlayerStatSchema.goals_conceded,
            labeled,
        )
        .join(PlayerStatSchema, PlayerStatSchema.player_id == PlayerSchema.player_id)
        .join(NationalTeamSchema, NationalTeamSchema.team_id == PlayerSchema.team_id)
    )
    if filters:
        stmt = stmt.where(*filters)
    stmt = stmt.order_by(*_sort_order(labeled, request, PlayerStatSchema.minutes_played)).limit(
        request.limit
    )
    raw_rows = (await session.execute(stmt)).all()
    return _build_ranking(request, raw_rows)


def _club_where(request: QueryPlayerStatsRequest) -> list:
    filters = [PlayerIdentityLinkSchema.status == LinkReviewStatus.APPROVED]
    if request.competition_id is not None:
        filters.append(RealPlayerSeasonStatSchema.competition_id == request.competition_id)
    if used_fields(request.sort_by, request.filters) & GK_ONLY_FIELDS:
        filters.append(PlayerSchema.position.ilike("G%"))
    for item in request.filters:
        if item.field in ROSTER_FIELDS:
            filters.append(_roster_clause(item))
    return filters


def _club_having(request: QueryPlayerStatsRequest, aggregates: dict) -> list:
    clauses: list = []
    fields = used_fields(request.sort_by, request.filters)
    minutes = aggregates[PlayerStatField.MINUTES]
    if fields & PER90_FIELDS:
        clauses.append(minutes > 0)
    for item in request.filters:
        if item.field in ROSTER_FIELDS:
            continue
        clauses.append(_stat_clause(aggregates[item.field], item))
    return clauses


async def query_club_seasons(
    session: AsyncSession, request: QueryPlayerStatsRequest
) -> PlayerRanking:
    if not request.season_years:
        return _build_ranking(request, [])

    stat = RealPlayerSeasonStatSchema
    year_expr = season_start_year_expr(stat.season)
    base_filters = _club_where(request)
    year_filter = year_expr.in_(request.season_years)

    aggregates = club_stat_aggregates()
    sort_expr = aggregates.get(request.sort_by)
    if sort_expr is None:
        raise RankingQueryError(f"Cannot sort club stats by '{request.sort_by}'.")
    minutes_sum = aggregates[PlayerStatField.MINUTES]
    appearances_sum = aggregates[PlayerStatField.APPEARANCES]
    labeled = sort_expr.label("sort_value")
    having_clauses = _club_having(request, aggregates)

    stmt: Select[Any] = (
        select(
            PlayerSchema.player_id,
            PlayerSchema.player_name,
            PlayerSchema.position,
            PlayerSchema.club_team,
            PlayerSchema.height_cm,
            age_years_expr().label("age"),
            team_code_expr().label("team_code"),
            appearances_sum.label("appearances"),
            minutes_sum.label("minutes"),
            aggregates[PlayerStatField.GOALS].label("goals"),
            aggregates[PlayerStatField.ASSISTS].label("assists"),
            aggregates[PlayerStatField.YELLOW_CARDS].label("yellow_cards"),
            aggregates[PlayerStatField.RED_CARDS].label("red_cards"),
            labeled,
        )
        .join(
            PlayerIdentityLinkSchema,
            PlayerIdentityLinkSchema.player_id == PlayerSchema.player_id,
        )
        .join(stat, stat.real_player_id == PlayerIdentityLinkSchema.real_player_id)
        .join(NationalTeamSchema, NationalTeamSchema.team_id == PlayerSchema.team_id)
        .where(*base_filters, year_filter)
        .group_by(
            PlayerSchema.player_id,
            PlayerSchema.player_name,
            PlayerSchema.position,
            PlayerSchema.club_team,
            PlayerSchema.height_cm,
            PlayerSchema.date_of_birth,
            NationalTeamSchema.fifa_code,
            NationalTeamSchema.team_name,
        )
        .order_by(*_sort_order(labeled, request, minutes_sum))
        .limit(request.limit)
    )
    if having_clauses:
        stmt = stmt.having(and_(*having_clauses))
    raw_rows = (await session.execute(stmt)).all()
    return _build_ranking(request, raw_rows)


async def query_player_stats(
    session: AsyncSession, request: QueryPlayerStatsRequest
) -> PlayerRanking:
    if request.dataset == QueryDataset.WORLD_CUP:
        return await query_world_cup(session, request)
    return await query_club_seasons(session, request)
