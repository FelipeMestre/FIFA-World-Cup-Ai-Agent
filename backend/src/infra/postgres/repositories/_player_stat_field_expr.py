"""SQL expressions for `query_player_stats` field catalog."""

from sqlalchemy import Integer, case, cast, func, literal, or_

from src.domain.player_analytics.model.player_ranking import (
    WORLD_CUP_AGE_AS_OF,
    FilterOp,
    PlayerStatField,
)
from src.infra.postgres.schemas.national_team_schema import NationalTeamSchema
from src.infra.postgres.schemas.player_schema import PlayerSchema, PlayerStatSchema
from src.infra.postgres.schemas.real_player_schema import RealPlayerSeasonStatSchema

_POSITION_LETTER = {"GK": "G", "DEF": "D", "MID": "M", "FWD": "F"}


def season_start_year_expr(season_col):
    head = func.split_part(season_col, "/", 1)
    return case(
        (head.op("~")(r"^\d{2}$"), 2000 + cast(head, Integer)),
        (head.op("~")(r"^\d{4}$"), cast(head, Integer)),
        else_=None,
    )


def age_years_expr():
    return func.date_part(
        "year",
        func.age(literal(WORLD_CUP_AGE_AS_OF), PlayerSchema.date_of_birth),
    )


def team_code_expr():
    return func.coalesce(
        NationalTeamSchema.fifa_code,
        func.upper(func.substr(NationalTeamSchema.team_name, 1, 3)),
    )


def per90(total, minutes):
    return case((minutes > 0, total * 90.0 / minutes), else_=None)


def compare(expr, op: FilterOp, value):
    if op == FilterOp.EQ:
        return expr == value
    if op == FilterOp.GTE:
        return expr >= value
    return expr <= value


def position_match(value: str):
    code = str(value).strip().upper()
    letter = _POSITION_LETTER.get(code)
    if letter is None:
        raise ValueError("position must be GK, DEF, MID, or FWD.")
    return PlayerSchema.position.ilike(f"{letter}%")


def nationality_match(value: str):
    nationality = str(value).strip()
    return or_(
        func.unaccent(NationalTeamSchema.team_name).ilike(func.unaccent(nationality)),
        func.unaccent(NationalTeamSchema.fifa_code).ilike(func.unaccent(nationality)),
    )


def world_cup_stat_expr(field: PlayerStatField):
    stat = PlayerStatSchema
    minutes = stat.minutes_played
    mapping = {
        PlayerStatField.APPEARANCES: stat.matches_played,
        PlayerStatField.MINUTES: minutes,
        PlayerStatField.GOALS: stat.goals,
        PlayerStatField.ASSISTS: stat.assists,
        PlayerStatField.GOAL_CONTRIBUTIONS: stat.goals + stat.assists,
        PlayerStatField.GOALS_PER90: per90(stat.goals, minutes),
        PlayerStatField.ASSISTS_PER90: per90(stat.assists, minutes),
        PlayerStatField.GOAL_CONTRIBUTIONS_PER90: per90(stat.goals + stat.assists, minutes),
        PlayerStatField.YELLOW_CARDS: stat.yellow_cards,
        PlayerStatField.RED_CARDS: stat.red_cards,
        PlayerStatField.STARTS: stat.matches_started,
        PlayerStatField.PENALTY_GOALS: stat.penalty_goals,
        PlayerStatField.SAVES: stat.saves,
        PlayerStatField.SAVES_PER90: per90(func.coalesce(stat.saves, 0), minutes),
        PlayerStatField.CLEAN_SHEETS: stat.clean_sheets,
        PlayerStatField.GOALS_CONCEDED: stat.goals_conceded,
        PlayerStatField.GOALS_CONCEDED_PER90: per90(func.coalesce(stat.goals_conceded, 0), minutes),
        PlayerStatField.AGE: age_years_expr(),
        PlayerStatField.HEIGHT_CM: PlayerSchema.height_cm,
        PlayerStatField.POSITION: PlayerSchema.position,
        PlayerStatField.NATIONALITY: team_code_expr(),
    }
    return mapping.get(field)


def club_stat_aggregates() -> dict[PlayerStatField, object]:
    stat = RealPlayerSeasonStatSchema
    goals = func.sum(stat.goals)
    assists = func.sum(stat.assists)
    minutes = func.sum(stat.minutes_played)
    appearances = func.sum(stat.appearances)
    yellows = func.sum(stat.yellow_cards)
    reds = func.sum(stat.red_cards)
    return {
        PlayerStatField.APPEARANCES: appearances,
        PlayerStatField.MINUTES: minutes,
        PlayerStatField.GOALS: goals,
        PlayerStatField.ASSISTS: assists,
        PlayerStatField.GOAL_CONTRIBUTIONS: goals + assists,
        PlayerStatField.GOALS_PER90: per90(goals, minutes),
        PlayerStatField.ASSISTS_PER90: per90(assists, minutes),
        PlayerStatField.GOAL_CONTRIBUTIONS_PER90: per90(goals + assists, minutes),
        PlayerStatField.YELLOW_CARDS: yellows,
        PlayerStatField.RED_CARDS: reds,
        PlayerStatField.AGE: age_years_expr(),
        PlayerStatField.HEIGHT_CM: PlayerSchema.height_cm,
        PlayerStatField.POSITION: PlayerSchema.position,
        PlayerStatField.NATIONALITY: team_code_expr(),
    }
