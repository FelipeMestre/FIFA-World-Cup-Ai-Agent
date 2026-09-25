"""SQL-first aggregation for the `get_team_analysis` chat tool.

`match_event.event_type` uses the literal values `"Yellow Card"` /
`"Red Card"` (Title Case, confirmed against the real ingested dataset via
`SELECT DISTINCT event_type FROM match_event`) -- no enum/constant pins
this down elsewhere in the codebase yet, so a schema change there would
silently break `_YELLOW_CARD`/`_RED_CARD` below.

`standing_label`'s narrative ("Runners-up · out 0-1 to Spain") is built
from the team's *last* match's `tournament_stage.stage_name` and outcome,
not from a real "furthest stage reached" concept -- there's no
stage-ordering or elimination flag in the schema to derive a proper
noun-form from a stage name, so this returns the stage name as-is instead
of guessing a transformation. Verified live against real tournament data:
renders correctly as e.g. "Final · out 0–1 to Spain" for a runner-up.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.chat.exceptions.chat_exceptions import (
    SameTeamComparisonError,
    TeamNotFoundError,
)
from src.domain.team_analytics.model.base import ResultLetter, TeamMatchResult, TeamRecord
from src.domain.team_analytics.model.team_analysis import (
    StatWithFieldAverage,
    TeamAnalysis,
    TeamDiscipline,
    TeamGoalsByMatch,
)
from src.domain.team_analytics.model.team_comparison import TeamComparison
from src.infra.postgres.config import get_db
from src.infra.postgres.interfaces.team_analytics_repository_interface import (
    TeamAnalyticsRepositoryInterface,
)
from src.infra.postgres.repositories._team_comparison_query import (
    load_team_comparison,
    load_team_side,
)
from src.infra.postgres.schemas.match_schema import (
    MatchEventSchema,
    MatchSchema,
    MatchTeamStatSchema,
)
from src.infra.postgres.schemas.national_team_schema import NationalTeamSchema
from src.infra.postgres.schemas.reference_schema import TournamentStageSchema

_YELLOW_CARD = "Yellow Card"
_RED_CARD = "Red Card"

# (display label, `match_team_stat` column, unit suffix)
_STAT_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("Possession", "possession_pct", "%"),
    ("Shots", "total_shots", ""),
    ("Shots on target", "shots_on_target", ""),
    ("Corners", "corners", ""),
    ("Fouls", "fouls", ""),
    ("Offsides", "offsides", ""),
)

_MatchRow = tuple[MatchSchema, str]  # (match, stage_name)


class _SqlAlchemyTeamAnalyticsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_team_analysis(self, team_query: str) -> TeamAnalysis | None:
        team_row = await self._resolve_team(team_query)
        if team_row is None:
            return None

        team_id = team_row.team_id
        match_rows = await self._get_team_matches(team_id)
        opponent_ids = {
            (m.away_team_id if m.home_team_id == team_id else m.home_team_id)
            for m, _stage in match_rows
        }
        opponent_names = await self._get_team_names(opponent_ids)

        stat_rows = await self._get_team_match_stats(team_id)
        field_averages = await self._get_field_averages()
        event_counts = await self._get_event_counts(team_id)
        field_yellow_per_match = await self._get_field_yellow_per_match()

        match_count = len(match_rows)
        record = _build_record(team_id, match_rows)
        fouls_total = sum(row.fouls for row in stat_rows)
        side = await load_team_side(self._session, team_row)

        return TeamAnalysis(
            id=str(team_row.team_id),
            code=team_row.fifa_code or team_row.team_name[:3].upper(),
            name=team_row.team_name,
            scope_label=f"WC 2026 · {match_count} matches",
            standing_label=_build_standing_label(team_id, match_rows, opponent_names),
            record=record,
            goal_difference=record.goals_for - record.goals_against,
            conceded_per_game=(
                round(record.goals_against / match_count, 2) if match_count else 0.0
            ),
            clean_sheets=_count_clean_sheets(team_id, match_rows),
            avg_possession_pct=_avg([row.possession_pct for row in stat_rows]),
            goals_by_match=_build_goals_by_match(team_id, match_rows, opponent_names),
            tournament_averages=_build_tournament_averages(stat_rows, field_averages)
            + side.extra_averages,
            match_results=_build_match_results(team_id, match_rows, opponent_names),
            discipline=_build_discipline(
                event_counts, fouls_total, match_count, field_yellow_per_match
            ),
            stage_caption=_build_stage_caption(match_rows),
            confederation=side.identity.confederation,
            group_letter=side.identity.group_letter,
            manager_name=side.identity.manager_name,
            fifa_ranking_pre_tournament=side.identity.fifa_ranking_pre_tournament,
            squad=side.identity.squad,
            group=side.identity.group,
            top_scorer=side.identity.top_scorer,
            top_assister=side.identity.top_assister,
            most_minutes=side.identity.most_minutes,
            positions=side.positions,
        )

    async def get_team_comparison(self, team_a_query: str, team_b_query: str) -> TeamComparison:
        team_a = await self._require_team(team_a_query)
        team_b = await self._require_team(team_b_query)
        if team_a.team_id == team_b.team_id:
            raise SameTeamComparisonError(
                f"'{team_a_query}' and '{team_b_query}' both resolved to "
                f"{team_a.team_name} -- pick two different teams to compare."
            )
        return await load_team_comparison(self._session, team_a, team_b)

    async def _require_team(self, team_query: str) -> NationalTeamSchema:
        team = await self._resolve_team(team_query)
        if team is None:
            raise TeamNotFoundError(f"No team found matching '{team_query}'.")
        return team

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

    async def _get_team_matches(self, team_id: int) -> list[_MatchRow]:
        stmt = (
            select(MatchSchema, TournamentStageSchema.stage_name)
            .join(TournamentStageSchema, TournamentStageSchema.stage_id == MatchSchema.stage_id)
            .where(or_(MatchSchema.home_team_id == team_id, MatchSchema.away_team_id == team_id))
            .order_by(MatchSchema.date, MatchSchema.kickoff_time_utc)
        )
        result = await self._session.execute(stmt)
        return [(row.MatchSchema, row.stage_name) for row in result.all()]

    async def _get_team_names(self, team_ids: set[int]) -> dict[int, tuple[str, str]]:
        if not team_ids:
            return {}
        stmt = select(NationalTeamSchema).where(NationalTeamSchema.team_id.in_(team_ids))
        result = await self._session.execute(stmt)
        return {
            row.team_id: (row.fifa_code or row.team_name[:3].upper(), row.team_name)
            for row in result.scalars().all()
        }

    async def _get_team_match_stats(self, team_id: int) -> list[MatchTeamStatSchema]:
        stmt = select(MatchTeamStatSchema).where(MatchTeamStatSchema.team_id == team_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def _get_field_averages(self) -> dict[str, float]:
        columns = [
            func.avg(getattr(MatchTeamStatSchema, attr)) for _label, attr, _suffix in _STAT_FIELDS
        ]
        row = (await self._session.execute(select(*columns))).one()
        return {
            attr: float(value) if value is not None else 0.0
            for (_label, attr, _suffix), value in zip(_STAT_FIELDS, row, strict=True)
        }

    async def _get_event_counts(self, team_id: int) -> dict[str, int]:
        stmt = (
            select(MatchEventSchema.event_type, func.count())
            .where(
                MatchEventSchema.team_id == team_id,
                MatchEventSchema.event_type.in_((_YELLOW_CARD, _RED_CARD)),
            )
            .group_by(MatchEventSchema.event_type)
        )
        result = await self._session.execute(stmt)
        return dict(result.tuples().all())

    async def _get_field_yellow_per_match(self) -> float:
        yellow_count = (
            await self._session.execute(
                select(func.count())
                .select_from(MatchEventSchema)
                .where(MatchEventSchema.event_type == _YELLOW_CARD)
            )
        ).scalar_one()
        match_count = (
            await self._session.execute(select(func.count()).select_from(MatchSchema))
        ).scalar_one()
        # Two teams per match; divide by team-match instances, not raw match count,
        # to stay comparable with a single team's own yellow_per_match.
        team_match_instances = match_count * 2
        return round(yellow_count / team_match_instances, 2) if team_match_instances else 0.0


def _match_outcome(match: MatchSchema, team_id: int) -> ResultLetter:
    """W/D/L from `team_id`'s perspective. A regulation draw decided by
    penalties is scored by the penalty result, never left as a draw."""
    is_home = match.home_team_id == team_id
    if match.home_penalty_score is not None and match.away_penalty_score is not None:
        team_pens = match.home_penalty_score if is_home else match.away_penalty_score
        opponent_pens = match.away_penalty_score if is_home else match.home_penalty_score
        return "W" if team_pens > opponent_pens else "L"

    team_score = match.home_score if is_home else match.away_score
    opponent_score = match.away_score if is_home else match.home_score
    if team_score > opponent_score:
        return "W"
    if team_score < opponent_score:
        return "L"
    return "D"


def _build_record(team_id: int, match_rows: list[_MatchRow]) -> TeamRecord:
    won = drawn = lost = goals_for = goals_against = 0
    for match, _stage_name in match_rows:
        is_home = match.home_team_id == team_id
        goals_for += match.home_score if is_home else match.away_score
        goals_against += match.away_score if is_home else match.home_score
        outcome = _match_outcome(match, team_id)
        if outcome == "W":
            won += 1
        elif outcome == "D":
            drawn += 1
        else:
            lost += 1
    return TeamRecord(
        won=won, drawn=drawn, lost=lost, goals_for=goals_for, goals_against=goals_against
    )


def _count_clean_sheets(team_id: int, match_rows: list[_MatchRow]) -> int:
    return sum(
        1
        for match, _stage_name in match_rows
        if (match.away_score if match.home_team_id == team_id else match.home_score) == 0
    )


def _build_goals_by_match(
    team_id: int, match_rows: list[_MatchRow], opponent_names: dict[int, tuple[str, str]]
) -> list[TeamGoalsByMatch]:
    rows = []
    for match, _stage_name in match_rows:
        is_home = match.home_team_id == team_id
        opponent_id = match.away_team_id if is_home else match.home_team_id
        opponent_code, _opponent_name = opponent_names.get(opponent_id, ("???", "Unknown"))
        rows.append(
            TeamGoalsByMatch(
                opponent_code=opponent_code,
                goals_for=match.home_score if is_home else match.away_score,
                goals_against=match.away_score if is_home else match.home_score,
            )
        )
    return rows


def _build_match_results(
    team_id: int, match_rows: list[_MatchRow], opponent_names: dict[int, tuple[str, str]]
) -> list[TeamMatchResult]:
    rows = []
    for match, stage_name in match_rows:
        is_home = match.home_team_id == team_id
        opponent_id = match.away_team_id if is_home else match.home_team_id
        opponent_code, opponent_name = opponent_names.get(opponent_id, ("???", "Unknown"))
        goals_for = match.home_score if is_home else match.away_score
        goals_against = match.away_score if is_home else match.home_score
        rows.append(
            TeamMatchResult(
                stage=stage_name,
                opponent_code=opponent_code,
                opponent_name=opponent_name,
                score=f"{goals_for}–{goals_against}",
                result=_match_outcome(match, team_id),
            )
        )
    return rows


def _build_tournament_averages(
    stat_rows: list[MatchTeamStatSchema], field_averages: dict[str, float]
) -> list[StatWithFieldAverage]:
    rows = []
    for label, attr, suffix in _STAT_FIELDS:
        team_avg = _avg([getattr(row, attr) for row in stat_rows])
        field_avg = field_averages[attr]
        delta = team_avg - field_avg
        glyph = "▲" if delta >= 0 else "▼"
        rows.append(
            StatWithFieldAverage(
                label=label,
                value=f"{team_avg:.1f}{suffix}",
                field_value=f"{field_avg:.1f}{suffix}",
                delta=f"{glyph} {abs(delta):.1f}",
            )
        )
    return rows


def _build_discipline(
    event_counts: dict[str, int],
    fouls_total: int,
    match_count: int,
    field_yellow_per_match: float,
) -> TeamDiscipline:
    yellow_cards = event_counts.get(_YELLOW_CARD, 0)
    return TeamDiscipline(
        yellow_cards=yellow_cards,
        red_cards=event_counts.get(_RED_CARD, 0),
        fouls=fouls_total,
        yellow_per_match=round(yellow_cards / match_count, 2) if match_count else 0.0,
        field_yellow_per_match=field_yellow_per_match,
    )


def _build_stage_caption(match_rows: list[_MatchRow]) -> str:
    if not match_rows:
        return "Did not play"
    first_stage = match_rows[0][1]
    last_stage = match_rows[-1][1]
    return first_stage if first_stage == last_stage else f"{first_stage} to {last_stage}"


def _build_standing_label(
    team_id: int, match_rows: list[_MatchRow], opponent_names: dict[int, tuple[str, str]]
) -> str:
    if not match_rows:
        return "Did not qualify"

    last_match, last_stage = match_rows[-1]
    outcome = _match_outcome(last_match, team_id)
    if outcome != "L":
        return f"{last_stage} · unbeaten so far"

    is_home = last_match.home_team_id == team_id
    opponent_id = last_match.away_team_id if is_home else last_match.home_team_id
    _opponent_code, opponent_name = opponent_names.get(opponent_id, ("???", "Unknown"))
    team_score = last_match.home_score if is_home else last_match.away_score
    opponent_score = last_match.away_score if is_home else last_match.home_score
    return f"{last_stage} · out {team_score}–{opponent_score} to {opponent_name}"


def _avg(values: list[float | int]) -> float:
    return round(sum(values) / len(values), 2) if values else 0.0


def get_team_analytics_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TeamAnalyticsRepositoryInterface:
    return _SqlAlchemyTeamAnalyticsRepository(session)
