"""SQL fetch for `get_team_comparison`. Aggregation stays in Postgres; the
view module turns the rows into the read model.
"""

from sqlalchemy import and_, case, distinct, func, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.team_analytics.model.team_comparison import TeamComparison
from src.infra.postgres.repositories._team_comparison_facts import (
    DepthFact,
    FieldBenchmarks,
    GroupFact,
    MatchFact,
    PlayerFact,
    TeamProfile,
    TeamStatFact,
)
from src.infra.postgres.repositories._team_comparison_view import assemble_team_comparison
from src.infra.postgres.schemas.match_schema import (
    MatchEventSchema,
    MatchLineupSchema,
    MatchSchema,
    MatchTeamStatSchema,
)
from src.infra.postgres.schemas.national_team_schema import NationalTeamSchema
from src.infra.postgres.schemas.player_schema import PlayerSchema, PlayerStatSchema
from src.infra.postgres.schemas.reference_schema import TournamentStageSchema

_YELLOW_CARD = "Yellow Card"
_RED_CARD = "Red Card"


async def load_team_comparison(
    session: AsyncSession, team_a: NationalTeamSchema, team_b: NationalTeamSchema
) -> TeamComparison:
    team_ids = (team_a.team_id, team_b.team_id)
    matches = await _matches(session, team_ids)
    groups, field_group_points = await _group_table(session)
    return assemble_team_comparison(
        team_a=_profile(team_a),
        team_b=_profile(team_b),
        matches=matches,
        opponents=await _opponents(session, matches),
        team_stats=await _team_stats(session, team_ids),
        cards=await _cards(session, team_ids),
        players=await _players(session, team_ids),
        depth=await _depth(session, team_ids),
        groups=groups,
        field=await _field(session, field_group_points),
    )


def _profile(team: NationalTeamSchema) -> TeamProfile:
    return TeamProfile(
        team_id=team.team_id,
        name=team.team_name,
        fifa_code=team.fifa_code,
        confederation=team.confederation,
        group_letter=team.group_letter,
        manager_name=team.manager_name,
        fifa_ranking_pre_tournament=team.fifa_ranking_pre_tournament,
        elo_rating=team.elo_rating,
        transfermarkt_average_age=(None if team.average_age is None else float(team.average_age)),
        transfermarkt_market_value_eur=team.total_market_value_eur,
        transfermarkt_squad_size=team.squad_size,
    )


async def _matches(session: AsyncSession, team_ids: tuple[int, int]) -> list[MatchFact]:
    stmt = (
        select(MatchSchema, TournamentStageSchema.stage_name, TournamentStageSchema.is_knockout)
        .join(TournamentStageSchema, TournamentStageSchema.stage_id == MatchSchema.stage_id)
        .where(
            or_(
                MatchSchema.home_team_id.in_(team_ids),
                MatchSchema.away_team_id.in_(team_ids),
            )
        )
        .order_by(MatchSchema.date, MatchSchema.kickoff_time_utc, MatchSchema.match_id)
    )
    rows = []
    for match, stage_name, is_knockout in (await session.execute(stmt)).all():
        rows.append(
            MatchFact(
                match_id=match.match_id,
                stage_name=stage_name,
                is_knockout=is_knockout,
                home_team_id=match.home_team_id,
                away_team_id=match.away_team_id,
                home_score=match.home_score,
                away_score=match.away_score,
                home_penalty_score=match.home_penalty_score,
                away_penalty_score=match.away_penalty_score,
                home_xg=float(match.home_xg),
                away_xg=float(match.away_xg),
            )
        )
    return rows


async def _opponents(session: AsyncSession, matches: list[MatchFact]) -> dict[int, tuple[str, str]]:
    team_ids = {match.home_team_id for match in matches} | {match.away_team_id for match in matches}
    if not team_ids:
        return {}
    stmt = select(NationalTeamSchema).where(NationalTeamSchema.team_id.in_(team_ids))
    rows = (await session.execute(stmt)).scalars().all()
    return {
        row.team_id: (row.fifa_code or row.team_name[:3].upper(), row.team_name) for row in rows
    }


async def _team_stats(session: AsyncSession, team_ids: tuple[int, int]) -> list[TeamStatFact]:
    stmt = select(MatchTeamStatSchema).where(MatchTeamStatSchema.team_id.in_(team_ids))
    return [
        TeamStatFact(
            team_id=row.team_id,
            possession_pct=row.possession_pct,
            total_shots=row.total_shots,
            shots_on_target=row.shots_on_target,
            corners=row.corners,
            fouls=row.fouls,
            offsides=row.offsides,
            saves=row.saves,
        )
        for row in (await session.execute(stmt)).scalars().all()
    ]


async def _cards(session: AsyncSession, team_ids: tuple[int, int]) -> dict[int, tuple[int, int]]:
    stmt = (
        select(MatchEventSchema.team_id, MatchEventSchema.event_type, func.count())
        .where(
            MatchEventSchema.team_id.in_(team_ids),
            MatchEventSchema.event_type.in_((_YELLOW_CARD, _RED_CARD)),
        )
        .group_by(MatchEventSchema.team_id, MatchEventSchema.event_type)
    )
    by_team: dict[int, dict[str, int]] = {}
    for team_id, event_type, count in (await session.execute(stmt)).tuples():
        by_team.setdefault(team_id, {})[event_type] = int(count)
    return {
        team_id: (events.get(_YELLOW_CARD, 0), events.get(_RED_CARD, 0))
        for team_id, events in by_team.items()
    }


async def _players(session: AsyncSession, team_ids: tuple[int, int]) -> list[PlayerFact]:
    stmt = (
        select(PlayerSchema, PlayerStatSchema)
        .outerjoin(PlayerStatSchema, PlayerStatSchema.player_id == PlayerSchema.player_id)
        .where(PlayerSchema.team_id.in_(team_ids))
    )
    facts = []
    for player, stat in (await session.execute(stmt)).all():
        facts.append(
            PlayerFact(
                player_id=player.player_id,
                team_id=player.team_id,
                name=player.player_name,
                position=player.position,
                club=player.club_team,
                market_value_eur=player.market_value_eur,
                caps=player.caps,
                date_of_birth=player.date_of_birth,
                height_cm=player.height_cm,
                appearances=0 if stat is None else stat.matches_played,
                starts=0 if stat is None else stat.matches_started,
                minutes=0 if stat is None else stat.minutes_played,
                goals=0 if stat is None else stat.goals,
                assists=0 if stat is None else stat.assists,
                yellow_cards=0 if stat is None else stat.yellow_cards,
                red_cards=0 if stat is None else stat.red_cards,
                penalty_goals=0 if stat is None else stat.penalty_goals,
                own_goals=0 if stat is None else stat.own_goals,
                clean_sheets=None if stat is None else stat.clean_sheets,
                saves=None if stat is None else stat.saves,
                goals_conceded=None if stat is None else stat.goals_conceded,
            )
        )
    return facts


async def _depth(session: AsyncSession, team_ids: tuple[int, int]) -> dict[int, DepthFact]:
    starter = MatchLineupSchema.is_starting_xi.is_(True)
    stmt = (
        select(
            MatchLineupSchema.team_id,
            func.count(distinct(MatchLineupSchema.player_id)).filter(starter),
            func.coalesce(func.sum(MatchLineupSchema.minutes_played).filter(starter), 0),
            func.coalesce(func.sum(MatchLineupSchema.minutes_played), 0),
        )
        .where(MatchLineupSchema.team_id.in_(team_ids))
        .group_by(MatchLineupSchema.team_id)
    )
    return {
        team_id: DepthFact(int(starters), int(starter_minutes), int(total_minutes))
        for team_id, starters, starter_minutes, total_minutes in (
            await session.execute(stmt)
        ).tuples()
    }


def _points_expr(score, opponent_score, pens, opponent_pens):
    """3/1/0 from one side. A shootout replaces the draw, same rule as W/D/L."""
    pens_played = and_(pens.is_not(None), opponent_pens.is_not(None))
    return case(
        (pens_played, case((pens > opponent_pens, 3), else_=0)),
        (score > opponent_score, 3),
        (score == opponent_score, 1),
        else_=0,
    )


async def _group_table(session: AsyncSession) -> tuple[dict[int, GroupFact], float]:
    match = MatchSchema
    stage = TournamentStageSchema
    group_only = stage.is_knockout.is_(False)
    home = (
        select(
            match.home_team_id.label("team_id"),
            _points_expr(
                match.home_score,
                match.away_score,
                match.home_penalty_score,
                match.away_penalty_score,
            ).label("points"),
            (match.home_score - match.away_score).label("gd"),
        )
        .join(stage, stage.stage_id == match.stage_id)
        .where(group_only)
    )
    away = (
        select(
            match.away_team_id.label("team_id"),
            _points_expr(
                match.away_score,
                match.home_score,
                match.away_penalty_score,
                match.home_penalty_score,
            ).label("points"),
            (match.away_score - match.home_score).label("gd"),
        )
        .join(stage, stage.stage_id == match.stage_id)
        .where(group_only)
    )
    grouped = union_all(home, away).subquery()
    stmt = select(
        grouped.c.team_id,
        func.sum(grouped.c.points),
        func.sum(grouped.c.gd),
        func.count(),
    ).group_by(grouped.c.team_id)
    rows = {
        int(team_id): GroupFact(played=int(played), points=int(points), goal_difference=int(gd))
        for team_id, points, gd, played in (await session.execute(stmt)).tuples()
    }
    if not rows:
        return {}, 0.0
    return rows, round(sum(row.points for row in rows.values()) / len(rows), 2)


async def _field(session: AsyncSession, group_points: float) -> FieldBenchmarks:
    stat = (
        await session.execute(
            select(
                func.avg(MatchTeamStatSchema.possession_pct),
                func.avg(MatchTeamStatSchema.total_shots),
                func.avg(MatchTeamStatSchema.shots_on_target),
                func.avg(MatchTeamStatSchema.corners),
                func.avg(MatchTeamStatSchema.fouls),
                func.avg(MatchTeamStatSchema.offsides),
                func.avg(MatchTeamStatSchema.saves),
                func.coalesce(func.sum(MatchTeamStatSchema.total_shots), 0),
                func.coalesce(func.sum(MatchTeamStatSchema.shots_on_target), 0),
            )
        )
    ).one()
    match_row = (
        await session.execute(
            select(
                func.coalesce(func.sum(MatchSchema.home_score + MatchSchema.away_score), 0),
                func.coalesce(func.sum(MatchSchema.home_xg + MatchSchema.away_xg), 0),
                func.count(),
                func.count().filter(MatchSchema.away_score == 0),
                func.count().filter(MatchSchema.home_score == 0),
            )
        )
    ).one()
    yellows = (
        await session.execute(
            select(func.count())
            .select_from(MatchEventSchema)
            .where(MatchEventSchema.event_type == _YELLOW_CARD)
        )
    ).scalar_one()
    (
        possession,
        shots,
        on_target,
        corners,
        fouls,
        offsides,
        saves,
        shot_sum,
        on_target_sum,
    ) = stat
    total_goals, total_xg, match_count, home_clean_sheets, away_clean_sheets = match_row
    team_matches = int(match_count) * 2
    shot_total = float(shot_sum)
    on_target_total = float(on_target_sum)
    goals = float(total_goals)
    return FieldBenchmarks(
        goals_per_game=_rate(goals, team_matches),
        xg_per_game=_rate(float(total_xg), team_matches),
        possession_pct=_rate(float(possession or 0), 1),
        shots_per_game=_rate(float(shots or 0), 1),
        shots_on_target_per_game=_rate(float(on_target or 0), 1),
        shot_accuracy_pct=_percent(on_target_total, shot_total),
        conversion_pct=_percent(goals, on_target_total),
        clean_sheets_per_game=_rate(int(home_clean_sheets) + int(away_clean_sheets), team_matches),
        corners_per_game=_rate(float(corners or 0), 1),
        fouls_per_game=_rate(float(fouls or 0), 1),
        offsides_per_game=_rate(float(offsides or 0), 1),
        saves_per_game=_rate(float(saves or 0), 1),
        yellow_per_match=_rate(int(yellows), team_matches),
        group_points=group_points,
    )


def _rate(total: float, count: int) -> float:
    return round(total / count, 2) if count else 0.0


def _percent(part: float, whole: float) -> float:
    return round(part / whole * 100, 1) if whole else 0.0
