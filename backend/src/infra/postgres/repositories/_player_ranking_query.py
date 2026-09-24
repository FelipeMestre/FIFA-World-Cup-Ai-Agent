"""SQL ranking for `get_player_ranking`.

World Cup ranks `player_stat`. Transfermarkt ranks summed
`real_player_season_stat` rows for approved identity links. Season window
`latest` / `last_three` is the max start year among rows that already pass
roster and competition filters, so a filtered leaderboard is not emptied by
unrelated later seasons in the table.
"""

from typing import Any

from sqlalchemy import Integer, Select, and_, case, cast, desc, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.player_analytics.model.player_ranking import (
    ASCENDING_RANK_BY,
    GK_ONLY_RANK_BY,
    PER90_RANK_BY,
    WORLD_CUP_AGE_AS_OF,
    PlayerRanking,
    PlayerRankingRequest,
    RankBy,
    RankingScope,
    SeasonWindow,
)
from src.infra.postgres.repositories._player_ranking_rows import _build_ranking
from src.infra.postgres.repositories._player_stat_helpers import first_letter_for_position
from src.infra.postgres.schemas.national_team_schema import NationalTeamSchema
from src.infra.postgres.schemas.player_identity_link_schema import (
    LinkReviewStatus,
    PlayerIdentityLinkSchema,
)
from src.infra.postgres.schemas.player_schema import PlayerSchema, PlayerStatSchema
from src.infra.postgres.schemas.real_player_schema import RealPlayerSeasonStatSchema


def _season_start_year_expr(season_col):
    head = func.split_part(season_col, "/", 1)
    return case(
        (head.op("~")(r"^\d{2}$"), 2000 + cast(head, Integer)),
        (head.op("~")(r"^\d{4}$"), cast(head, Integer)),
        else_=None,
    )


def _age_years_expr():
    return func.date_part(
        "year",
        func.age(literal(WORLD_CUP_AGE_AS_OF), PlayerSchema.date_of_birth),
    )


def _team_code_expr():
    return func.coalesce(
        NationalTeamSchema.fifa_code,
        func.upper(func.substr(NationalTeamSchema.team_name, 1, 3)),
    )


def _roster_filters(request: PlayerRankingRequest) -> list:
    filters: list = []
    if request.position is not None:
        letter = first_letter_for_position(request.position)
        filters.append(PlayerSchema.position.ilike(f"{letter}%"))
    if request.age_min is not None:
        filters.append(_age_years_expr() >= request.age_min)
    if request.age_max is not None:
        filters.append(_age_years_expr() <= request.age_max)
    if request.height_min_cm is not None:
        filters.append(PlayerSchema.height_cm >= request.height_min_cm)
    if request.height_max_cm is not None:
        filters.append(PlayerSchema.height_cm <= request.height_max_cm)
    if request.nationality:
        nationality = request.nationality.strip()
        filters.append(
            or_(
                func.unaccent(NationalTeamSchema.team_name).ilike(func.unaccent(nationality)),
                func.unaccent(NationalTeamSchema.fifa_code).ilike(func.unaccent(nationality)),
            )
        )
    if request.rank_by in GK_ONLY_RANK_BY:
        filters.append(PlayerSchema.position.ilike("G%"))
    return filters


def _per90(total, minutes):
    return case((minutes > 0, total * 90.0 / minutes), else_=None)


def _world_cup_metric(rank_by: RankBy):
    stat = PlayerStatSchema
    minutes = stat.minutes_played
    metrics = {
        RankBy.GOALS: stat.goals,
        RankBy.ASSISTS: stat.assists,
        RankBy.GOAL_CONTRIBUTIONS: stat.goals + stat.assists,
        RankBy.GOALS_PER90: _per90(stat.goals, minutes),
        RankBy.ASSISTS_PER90: _per90(stat.assists, minutes),
        RankBy.GOAL_CONTRIBUTIONS_PER90: _per90(stat.goals + stat.assists, minutes),
        RankBy.PENALTY_GOALS: stat.penalty_goals,
        RankBy.MINUTES: minutes,
        RankBy.APPEARANCES: stat.matches_played,
        RankBy.STARTS: stat.matches_started,
        RankBy.YELLOW_CARDS: stat.yellow_cards,
        RankBy.RED_CARDS: stat.red_cards,
        RankBy.FEWEST_YELLOW_CARDS: stat.yellow_cards,
        RankBy.FEWEST_RED_CARDS: stat.red_cards,
        RankBy.SAVES: stat.saves,
        RankBy.SAVES_PER90: _per90(func.coalesce(stat.saves, 0), minutes),
        RankBy.CLEAN_SHEETS: stat.clean_sheets,
        RankBy.GOALS_CONCEDED: stat.goals_conceded,
        RankBy.GOALS_CONCEDED_PER90: _per90(func.coalesce(stat.goals_conceded, 0), minutes),
    }
    return metrics[rank_by]


def _world_cup_metric_filters(rank_by: RankBy) -> list:
    stat = PlayerStatSchema
    filters: list = []
    if rank_by in PER90_RANK_BY:
        filters.append(stat.minutes_played > 0)
    if rank_by in {RankBy.SAVES, RankBy.SAVES_PER90}:
        filters.append(stat.saves.is_not(None))
    if rank_by == RankBy.CLEAN_SHEETS:
        filters.append(stat.clean_sheets.is_not(None))
    if rank_by in {RankBy.GOALS_CONCEDED, RankBy.GOALS_CONCEDED_PER90}:
        filters.append(stat.goals_conceded.is_not(None))
    return filters


def _world_cup_stat_floors(request: PlayerRankingRequest) -> list:
    stat = PlayerStatSchema
    filters: list = []
    if request.min_appearances is not None:
        filters.append(stat.matches_played >= request.min_appearances)
    if request.min_minutes is not None:
        filters.append(stat.minutes_played >= request.min_minutes)
    if request.min_goals is not None:
        filters.append(stat.goals >= request.min_goals)
    if request.min_assists is not None:
        filters.append(stat.assists >= request.min_assists)
    return filters


def _order(sort_expr, request: PlayerRankingRequest):
    primary = sort_expr.asc() if request.rank_by in ASCENDING_RANK_BY else desc(sort_expr)
    return primary.nulls_last(), desc(PlayerStatSchema.minutes_played), PlayerSchema.player_id


async def rank_world_cup(session: AsyncSession, request: PlayerRankingRequest) -> PlayerRanking:
    sort_expr = _world_cup_metric(request.rank_by).label("sort_value")
    filters = [
        *_roster_filters(request),
        *_world_cup_metric_filters(request.rank_by),
        *_world_cup_stat_floors(request),
    ]
    stmt = (
        select(
            PlayerSchema.player_id,
            PlayerSchema.player_name,
            PlayerSchema.position,
            PlayerSchema.club_team,
            PlayerSchema.height_cm,
            _age_years_expr().label("age"),
            _team_code_expr().label("team_code"),
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
            sort_expr,
        )
        .join(PlayerStatSchema, PlayerStatSchema.player_id == PlayerSchema.player_id)
        .join(NationalTeamSchema, NationalTeamSchema.team_id == PlayerSchema.team_id)
    )
    if filters:
        stmt = stmt.where(*filters)
    stmt = stmt.order_by(*_order(sort_expr, request)).limit(request.limit)
    raw_rows = (await session.execute(stmt)).all()
    return _build_ranking(request, raw_rows)


def _club_totals(rank_by: RankBy):
    stat = RealPlayerSeasonStatSchema
    goals = func.sum(stat.goals)
    assists = func.sum(stat.assists)
    minutes = func.sum(stat.minutes_played)
    appearances = func.sum(stat.appearances)
    yellows = func.sum(stat.yellow_cards)
    reds = func.sum(stat.red_cards)
    metrics = {
        RankBy.GOALS: goals,
        RankBy.ASSISTS: assists,
        RankBy.GOAL_CONTRIBUTIONS: goals + assists,
        RankBy.GOALS_PER90: _per90(goals, minutes),
        RankBy.ASSISTS_PER90: _per90(assists, minutes),
        RankBy.GOAL_CONTRIBUTIONS_PER90: _per90(goals + assists, minutes),
        RankBy.MINUTES: minutes,
        RankBy.APPEARANCES: appearances,
        RankBy.YELLOW_CARDS: yellows,
        RankBy.RED_CARDS: reds,
        RankBy.FEWEST_YELLOW_CARDS: yellows,
        RankBy.FEWEST_RED_CARDS: reds,
    }
    return metrics[rank_by], minutes, appearances


def _club_base_filters(request: PlayerRankingRequest) -> list:
    stat = RealPlayerSeasonStatSchema
    filters = [
        PlayerIdentityLinkSchema.status == LinkReviewStatus.APPROVED,
        *_roster_filters(request),
    ]
    if request.competition_id is not None:
        filters.append(stat.competition_id == request.competition_id)
    return filters


async def rank_transfermarkt(session: AsyncSession, request: PlayerRankingRequest) -> PlayerRanking:
    stat = RealPlayerSeasonStatSchema
    year_expr = _season_start_year_expr(stat.season)
    base_filters = _club_base_filters(request)
    max_year_stmt = (
        select(func.max(year_expr))
        .select_from(PlayerSchema)
        .join(
            PlayerIdentityLinkSchema,
            PlayerIdentityLinkSchema.player_id == PlayerSchema.player_id,
        )
        .join(stat, stat.real_player_id == PlayerIdentityLinkSchema.real_player_id)
        .join(NationalTeamSchema, NationalTeamSchema.team_id == PlayerSchema.team_id)
        .where(*base_filters)
    )
    max_year = (await session.execute(max_year_stmt)).scalar_one_or_none()
    if max_year is None:
        return _build_ranking(request, [])

    if request.season_window == SeasonWindow.LATEST:
        year_filter = year_expr == max_year
    else:
        year_filter = year_expr >= (max_year - 2)

    sort_expr, minutes_sum, appearances_sum = _club_totals(request.rank_by)
    goals_sum = func.sum(stat.goals)
    assists_sum = func.sum(stat.assists)
    yellows_sum = func.sum(stat.yellow_cards)
    reds_sum = func.sum(stat.red_cards)
    sort_labeled = sort_expr.label("sort_value")
    having_clauses = []
    if request.rank_by in PER90_RANK_BY:
        having_clauses.append(minutes_sum > 0)
    if request.min_appearances is not None:
        having_clauses.append(appearances_sum >= request.min_appearances)
    if request.min_minutes is not None:
        having_clauses.append(minutes_sum >= request.min_minutes)
    if request.min_goals is not None:
        having_clauses.append(goals_sum >= request.min_goals)
    if request.min_assists is not None:
        having_clauses.append(assists_sum >= request.min_assists)

    stmt: Select[Any] = (
        select(
            PlayerSchema.player_id,
            PlayerSchema.player_name,
            PlayerSchema.position,
            PlayerSchema.club_team,
            PlayerSchema.height_cm,
            _age_years_expr().label("age"),
            _team_code_expr().label("team_code"),
            appearances_sum.label("appearances"),
            minutes_sum.label("minutes"),
            goals_sum.label("goals"),
            assists_sum.label("assists"),
            yellows_sum.label("yellow_cards"),
            reds_sum.label("red_cards"),
            sort_labeled,
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
        .order_by(
            (
                sort_labeled.asc() if request.rank_by in ASCENDING_RANK_BY else desc(sort_labeled)
            ).nulls_last(),
            desc(minutes_sum),
            PlayerSchema.player_id,
        )
        .limit(request.limit)
    )
    if having_clauses:
        stmt = stmt.having(and_(*having_clauses))
    raw_rows = (await session.execute(stmt)).all()
    return _build_ranking(request, raw_rows)


async def get_player_ranking(session: AsyncSession, request: PlayerRankingRequest) -> PlayerRanking:
    if request.scope == RankingScope.WORLD_CUP:
        return await rank_world_cup(session, request)
    return await rank_transfermarkt(session, request)
