"""Build one side of a team comparison from that team's matches, stats, and squad."""

from collections.abc import Callable
from datetime import date

from src.domain.player_analytics.model.player_ranking import WORLD_CUP_AGE_AS_OF
from src.domain.team_analytics.model.team_analysis import ResultLetter, TeamMatchResult, TeamRecord
from src.domain.team_analytics.model.team_comparison import (
    ComparedTeam,
    GroupOutcome,
    SquadLeader,
    SquadProfile,
    TeamDisciplineSummary,
    TeamRates,
)
from src.infra.postgres.repositories._player_stat_helpers import normalize_position
from src.infra.postgres.repositories._team_comparison_facts import (
    DepthFact,
    GroupFact,
    MatchFact,
    PlayerFact,
    TeamProfile,
    TeamStatFact,
)

_EMPTY_GROUP = GroupFact(played=0, points=0, goal_difference=0)
_EMPTY_DEPTH = DepthFact(distinct_starters=0, starter_minutes=0, total_minutes=0)


def team_matches(team_id: int, matches: list[MatchFact]) -> list[MatchFact]:
    return [match for match in matches if team_id in (match.home_team_id, match.away_team_id)]


def is_home(match: MatchFact, team_id: int) -> bool:
    return match.home_team_id == team_id


def score_for(match: MatchFact, team_id: int) -> int:
    return match.home_score if is_home(match, team_id) else match.away_score


def score_against(match: MatchFact, team_id: int) -> int:
    return match.away_score if is_home(match, team_id) else match.home_score


def outcome(match: MatchFact, team_id: int) -> ResultLetter:
    """W/D/L from `team_id`'s perspective. A draw decided by penalties is a
    win or a loss, matching `get_team_analysis`.
    """
    home = is_home(match, team_id)
    if match.home_penalty_score is not None and match.away_penalty_score is not None:
        team_pens = match.home_penalty_score if home else match.away_penalty_score
        opponent_pens = match.away_penalty_score if home else match.home_penalty_score
        return "W" if team_pens > opponent_pens else "L"
    team_score = score_for(match, team_id)
    opponent_score = score_against(match, team_id)
    if team_score > opponent_score:
        return "W"
    if team_score < opponent_score:
        return "L"
    return "D"


def per(total: float, count: int) -> float:
    return round(total / count, 2) if count else 0.0


def share_pct(part: float, whole: float) -> float:
    return round(part / whole * 100, 1) if whole else 0.0


def completed_age(born: date, as_of: date) -> int:
    years = as_of.year - born.year
    if (as_of.month, as_of.day) < (born.month, born.day):
        years -= 1
    return years


def build_compared_team(
    profile: TeamProfile,
    matches: list[MatchFact],
    opponents: dict[int, tuple[str, str]],
    team_stats: list[TeamStatFact],
    cards: dict[int, tuple[int, int]],
    players: list[PlayerFact],
    depth: dict[int, DepthFact],
    groups: dict[int, GroupFact],
) -> ComparedTeam:
    played = team_matches(profile.team_id, matches)
    record, goal_difference, rates, fouls = _record_and_rates(profile.team_id, played, team_stats)
    yellow, red = cards.get(profile.team_id, (0, 0))
    squad_players = [player for player in players if player.team_id == profile.team_id]
    group = groups.get(profile.team_id, _EMPTY_GROUP)
    return ComparedTeam(
        id=str(profile.team_id),
        code=profile.fifa_code or profile.name[:3].upper(),
        name=profile.name,
        confederation=profile.confederation,
        group_letter=profile.group_letter,
        manager_name=profile.manager_name,
        fifa_ranking_pre_tournament=profile.fifa_ranking_pre_tournament,
        elo_rating=profile.elo_rating,
        standing_label=_standing(profile.team_id, played, opponents),
        stage_caption=_stage_caption(played),
        record=record,
        goal_difference=goal_difference,
        rates=rates,
        discipline=TeamDisciplineSummary(
            yellow_cards=yellow,
            red_cards=red,
            fouls=fouls,
            yellow_per_match=per(yellow, len(played)),
        ),
        squad=_squad_profile(profile, squad_players, depth.get(profile.team_id, _EMPTY_DEPTH)),
        group=GroupOutcome(
            played=group.played, points=group.points, goal_difference=group.goal_difference
        ),
        match_results=_match_results(profile.team_id, played, opponents),
        top_scorer=_leader(squad_players, lambda player: player.goals),
        top_assister=_leader(squad_players, lambda player: player.assists),
        most_minutes=_leader(squad_players, lambda player: player.minutes),
    )


def _xg_for(match: MatchFact, team_id: int) -> float:
    return match.home_xg if is_home(match, team_id) else match.away_xg


def _xg_against(match: MatchFact, team_id: int) -> float:
    return match.away_xg if is_home(match, team_id) else match.home_xg


def _record_and_rates(
    team_id: int, played_matches: list[MatchFact], team_stats: list[TeamStatFact]
) -> tuple[TeamRecord, int, TeamRates, int]:
    won = drawn = lost = goals_for = goals_against = clean_sheets = 0
    xg_for = xg_against = 0.0
    for match in played_matches:
        goals_for += score_for(match, team_id)
        goals_against += score_against(match, team_id)
        xg_for += _xg_for(match, team_id)
        xg_against += _xg_against(match, team_id)
        if score_against(match, team_id) == 0:
            clean_sheets += 1
        result = outcome(match, team_id)
        if result == "W":
            won += 1
        elif result == "D":
            drawn += 1
        else:
            lost += 1
    played = len(played_matches)
    stats = [row for row in team_stats if row.team_id == team_id]
    samples = len(stats)
    shots = sum(row.total_shots for row in stats)
    on_target = sum(row.shots_on_target for row in stats)
    saves = sum(row.saves for row in stats)
    fouls = sum(row.fouls for row in stats)
    record = TeamRecord(
        won=won, drawn=drawn, lost=lost, goals_for=goals_for, goals_against=goals_against
    )
    rates = TeamRates(
        goals_per_game=per(goals_for, played),
        conceded_per_game=per(goals_against, played),
        xg_for=round(xg_for, 2),
        xg_against=round(xg_against, 2),
        xg_difference=round(xg_for - xg_against, 2),
        xg_per_game=per(xg_for, played),
        xg_against_per_game=per(xg_against, played),
        possession_pct=per(sum(row.possession_pct for row in stats), samples),
        shots_per_game=per(shots, samples),
        shots_on_target_per_game=per(on_target, samples),
        shot_accuracy_pct=share_pct(on_target, shots),
        conversion_pct=share_pct(goals_for, on_target),
        corners_per_game=per(sum(row.corners for row in stats), samples),
        fouls_per_game=per(fouls, samples),
        offsides_per_game=per(sum(row.offsides for row in stats), samples),
        saves=saves,
        saves_per_game=per(saves, samples),
        clean_sheets=clean_sheets,
        clean_sheets_per_game=per(clean_sheets, played),
    )
    return record, goals_for - goals_against, rates, fouls


def _standing(
    team_id: int, played_matches: list[MatchFact], opponents: dict[int, tuple[str, str]]
) -> str:
    if not played_matches:
        return "Did not qualify"
    last = played_matches[-1]
    if outcome(last, team_id) != "L":
        return f"{last.stage_name} · unbeaten so far"
    opponent_id = last.away_team_id if is_home(last, team_id) else last.home_team_id
    _code, opponent_name = opponents.get(opponent_id, ("???", "Unknown"))
    score = f"{score_for(last, team_id)}–{score_against(last, team_id)}"
    return f"{last.stage_name} · out {score} to {opponent_name}"


def _stage_caption(played_matches: list[MatchFact]) -> str:
    if not played_matches:
        return "Did not play"
    first = played_matches[0].stage_name
    last = played_matches[-1].stage_name
    return first if first == last else f"{first} to {last}"


def _match_results(
    team_id: int, played_matches: list[MatchFact], opponents: dict[int, tuple[str, str]]
) -> list[TeamMatchResult]:
    rows = []
    for match in played_matches:
        opponent_id = match.away_team_id if is_home(match, team_id) else match.home_team_id
        code, name = opponents.get(opponent_id, ("???", "Unknown"))
        rows.append(
            TeamMatchResult(
                stage=match.stage_name,
                opponent_code=code,
                opponent_name=name,
                score=f"{score_for(match, team_id)}–{score_against(match, team_id)}",
                result=outcome(match, team_id),
            )
        )
    return rows


def _squad_profile(
    profile: TeamProfile, players: list[PlayerFact], depth: DepthFact
) -> SquadProfile:
    ages = [completed_age(player.date_of_birth, WORLD_CUP_AGE_AS_OF) for player in players]
    values = sorted((player.market_value_eur for player in players), reverse=True)
    total_value = sum(values)
    roster = len(players)
    return SquadProfile(
        roster_size=roster,
        average_age=round(sum(ages) / roster, 1) if roster else None,
        total_market_value_eur=total_value,
        youngest_age=min(ages) if ages else None,
        oldest_age=max(ages) if ages else None,
        under_23_pct=share_pct(sum(1 for age in ages if age < 23), roster),
        over_30_pct=share_pct(sum(1 for age in ages if age > 30), roster),
        top_three_value_share_pct=share_pct(sum(values[:3]), total_value),
        distinct_starters=depth.distinct_starters,
        starter_minutes_share_pct=share_pct(depth.starter_minutes, depth.total_minutes),
        transfermarkt_average_age=profile.transfermarkt_average_age,
        transfermarkt_market_value_eur=profile.transfermarkt_market_value_eur,
        transfermarkt_squad_size=profile.transfermarkt_squad_size,
    )


def _leader(players: list[PlayerFact], score: Callable[[PlayerFact], int]) -> SquadLeader | None:
    eligible = [player for player in players if score(player) > 0]
    if not eligible:
        return None
    chosen = min(eligible, key=lambda player: (-score(player), -player.minutes, player.name))
    return SquadLeader(
        player_id=str(chosen.player_id),
        name=chosen.name,
        position=normalize_position(chosen.position),
        goals=chosen.goals,
        assists=chosen.assists,
        minutes=chosen.minutes,
    )
