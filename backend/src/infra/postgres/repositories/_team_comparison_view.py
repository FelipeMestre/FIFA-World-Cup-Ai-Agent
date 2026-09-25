"""Pure assembly of a `TeamComparison` from already-fetched facts.

Strengths and flaws are gaps, not prose. A note is kept only when the side
beats the other team by at least `_MIN_NORMALIZED_EDGE` of that metric's
scale and also sits on the better side of the tournament average. Corners
and offsides stay in `compared_stats` and are left out of the notes.
"""

from collections import defaultdict
from collections.abc import Callable
from typing import NamedTuple

from src.domain.player_analytics.model.player_ranking import WORLD_CUP_AGE_AS_OF
from src.domain.team_analytics.model.team_analysis import StatWithFieldAverage
from src.domain.team_analytics.model.team_comparison import (
    ComparedStat,
    ComparedTeam,
    ComparisonPlayer,
    ComparisonSide,
    Meeting,
    Position,
    PositionGroup,
    PositionRollup,
    PositionSquad,
    SideNote,
    TeamComparison,
)
from src.infra.postgres.repositories._player_stat_helpers import (
    normalize_position,
    per_ninety,
    player_initials,
)
from src.infra.postgres.repositories._team_comparison_facts import (
    DepthFact,
    FieldBenchmarks,
    GroupFact,
    MatchFact,
    PlayerFact,
    TeamProfile,
    TeamStatFact,
)
from src.infra.postgres.repositories._team_comparison_side import (
    build_compared_team,
    completed_age,
    is_home,
    outcome,
    per,
    team_matches,
)

_MIN_NORMALIZED_EDGE = 0.2
_NOTE_LIMIT = 3
_POSITIONS: tuple[Position, ...] = ("GK", "DEF", "MID", "FWD")


class _Metric(NamedTuple):
    label: str
    higher_is_better: bool
    scale: float
    counts_as_edge: bool
    format_value: Callable[[float], str]


def _fmt_rate(value: float) -> str:
    return f"{value:.2f}"


def _fmt_pct(value: float) -> str:
    return f"{value:.1f}%"


def _fmt_signed(value: float) -> str:
    return f"{value:+.2f}"


def _fmt_points(value: float) -> str:
    return f"{value:.0f}"


_METRICS: dict[str, _Metric] = {
    "goal_difference_per_game": _Metric("Goal difference / game", True, 1.0, True, _fmt_signed),
    "goals_per_game": _Metric("Goals per game", True, 1.0, True, _fmt_rate),
    "conceded_per_game": _Metric("Goals conceded / game", False, 1.0, True, _fmt_rate),
    "xg_difference_per_game": _Metric("xG difference / game", True, 0.5, True, _fmt_signed),
    "xg_per_game": _Metric("xG per game", True, 0.5, True, _fmt_rate),
    "xg_against_per_game": _Metric("xG against / game", False, 0.5, True, _fmt_rate),
    "possession_pct": _Metric("Possession", True, 10.0, True, _fmt_pct),
    "shots_per_game": _Metric("Shots per game", True, 4.0, True, _fmt_rate),
    "shots_on_target_per_game": _Metric("Shots on target / game", True, 2.0, True, _fmt_rate),
    "shot_accuracy_pct": _Metric("Shot accuracy", True, 10.0, True, _fmt_pct),
    "conversion_pct": _Metric("Conversion", True, 10.0, True, _fmt_pct),
    "clean_sheets_per_game": _Metric("Clean sheets / game", True, 0.5, True, _fmt_rate),
    "corners_per_game": _Metric("Corners per game", True, 2.0, False, _fmt_rate),
    "fouls_per_game": _Metric("Fouls per game", False, 3.0, True, _fmt_rate),
    "offsides_per_game": _Metric("Offsides per game", False, 1.0, False, _fmt_rate),
    "yellow_per_match": _Metric("Yellow cards / match", False, 1.0, True, _fmt_rate),
    "group_points": _Metric("Group points", True, 3.0, True, _fmt_points),
}


def assemble_team_comparison(
    *,
    team_a: TeamProfile,
    team_b: TeamProfile,
    matches: list[MatchFact],
    opponents: dict[int, tuple[str, str]],
    team_stats: list[TeamStatFact],
    cards: dict[int, tuple[int, int]],
    players: list[PlayerFact],
    depth: dict[int, DepthFact],
    groups: dict[int, GroupFact],
    field: FieldBenchmarks,
) -> TeamComparison:
    side_a = build_compared_team(
        team_a, matches, opponents, team_stats, cards, players, depth, groups
    )
    side_b = build_compared_team(
        team_b, matches, opponents, team_stats, cards, players, depth, groups
    )
    values_a = _metric_values(side_a, len(team_matches(team_a.team_id, matches)))
    values_b = _metric_values(side_b, len(team_matches(team_b.team_id, matches)))
    field_values = _field_values(field)
    group_edge = side_a.group.played == side_b.group.played and side_a.group.played > 0
    return TeamComparison(
        id=f"{team_a.team_id}-vs-{team_b.team_id}",
        scope_label="WC 2026",
        team_a=side_a,
        team_b=side_b,
        compared_stats=_compared_stats(values_a, values_b, field_values),
        strengths_and_flaws=_notes("a", values_a, values_b, field_values, group_edge)
        + _notes("b", values_b, values_a, field_values, group_edge),
        meetings=_meetings(team_a.team_id, team_b.team_id, matches),
        positions=_position_groups(team_a.team_id, team_b.team_id, players),
    )


_TILES_ALREADY_ON_ANALYSIS = {
    "possession_pct",
    "shots_per_game",
    "shots_on_target_per_game",
    "corners_per_game",
    "fouls_per_game",
    "offsides_per_game",
    "yellow_per_match",
}


def extra_field_average_rows(
    side: ComparedTeam, field: FieldBenchmarks, played: int
) -> list[StatWithFieldAverage]:
    """Comparison rates vs the tournament mean, skipping tiles analysis already has."""
    values = _metric_values(side, played)
    field_values = _field_values(field)
    rows = []
    for key, metric in _METRICS.items():
        if key in _TILES_ALREADY_ON_ANALYSIS:
            continue
        team_value = values[key]
        field_value = field_values[key]
        delta = team_value - field_value
        better = delta >= 0 if metric.higher_is_better else delta <= 0
        glyph = "▲" if better else "▼"
        rows.append(
            StatWithFieldAverage(
                label=metric.label,
                value=metric.format_value(team_value),
                field_value=metric.format_value(field_value),
                delta=f"{glyph} {abs(delta):.2f}",
            )
        )
    return rows


def position_squads_for_team(team_id: int, players: list[PlayerFact]) -> list[PositionSquad]:
    groups = _position_groups(team_id, -1, players)
    return [
        PositionSquad(
            position=group.position,
            players=group.team_a_players,
            rollup=group.team_a_rollup,
        )
        for group in groups
    ]


def _metric_values(side: ComparedTeam, played: int) -> dict[str, float]:
    rates = side.rates
    return {
        "goal_difference_per_game": per(side.goal_difference, played),
        "goals_per_game": rates.goals_per_game,
        "conceded_per_game": rates.conceded_per_game,
        "xg_difference_per_game": round(rates.xg_per_game - rates.xg_against_per_game, 2),
        "xg_per_game": rates.xg_per_game,
        "xg_against_per_game": rates.xg_against_per_game,
        "possession_pct": rates.possession_pct,
        "shots_per_game": rates.shots_per_game,
        "shots_on_target_per_game": rates.shots_on_target_per_game,
        "shot_accuracy_pct": rates.shot_accuracy_pct,
        "conversion_pct": rates.conversion_pct,
        "clean_sheets_per_game": rates.clean_sheets_per_game,
        "corners_per_game": rates.corners_per_game,
        "fouls_per_game": rates.fouls_per_game,
        "offsides_per_game": rates.offsides_per_game,
        "yellow_per_match": side.discipline.yellow_per_match,
        "group_points": float(side.group.points),
    }


def _field_values(field: FieldBenchmarks) -> dict[str, float]:
    return {
        "goal_difference_per_game": 0.0,
        "goals_per_game": field.goals_per_game,
        "conceded_per_game": field.goals_per_game,
        "xg_difference_per_game": 0.0,
        "xg_per_game": field.xg_per_game,
        "xg_against_per_game": field.xg_per_game,
        "possession_pct": field.possession_pct,
        "shots_per_game": field.shots_per_game,
        "shots_on_target_per_game": field.shots_on_target_per_game,
        "shot_accuracy_pct": field.shot_accuracy_pct,
        "conversion_pct": field.conversion_pct,
        "clean_sheets_per_game": field.clean_sheets_per_game,
        "corners_per_game": field.corners_per_game,
        "fouls_per_game": field.fouls_per_game,
        "offsides_per_game": field.offsides_per_game,
        "yellow_per_match": field.yellow_per_match,
        "group_points": field.group_points,
    }


def _compared_stats(
    values_a: dict[str, float], values_b: dict[str, float], field_values: dict[str, float]
) -> list[ComparedStat]:
    rows = []
    for key, metric in _METRICS.items():
        a_value = values_a[key]
        b_value = values_b[key]
        field_value = field_values[key]
        if metric.higher_is_better:
            a_better = a_value > b_value
            b_better = b_value > a_value
        else:
            a_better = a_value < b_value
            b_better = b_value < a_value
        rows.append(
            ComparedStat(
                label=metric.label,
                team_a_display=metric.format_value(a_value),
                team_b_display=metric.format_value(b_value),
                field_display=metric.format_value(field_value),
                team_a_value=a_value,
                team_b_value=b_value,
                field_value=field_value,
                higher_is_better=metric.higher_is_better,
                team_a_is_better=a_better,
                team_b_is_better=b_better,
            )
        )
    return rows


def _notes(
    side: ComparisonSide,
    own: dict[str, float],
    other: dict[str, float],
    field_values: dict[str, float],
    group_edge: bool,
) -> list[SideNote]:
    strengths: list[tuple[float, SideNote]] = []
    flaws: list[tuple[float, SideNote]] = []
    for key, metric in _METRICS.items():
        if not metric.counts_as_edge or (key == "group_points" and not group_edge):
            continue
        advantage = (own[key] - other[key]) / metric.scale
        versus_field = (own[key] - field_values[key]) / metric.scale
        if not metric.higher_is_better:
            advantage = -advantage
            versus_field = -versus_field
        detail = (
            f"{metric.format_value(own[key])} vs {metric.format_value(other[key])}"
            f" · field {metric.format_value(field_values[key])}"
        )
        note = SideNote(side=side, kind="strength", label=metric.label, detail=detail)
        if advantage >= _MIN_NORMALIZED_EDGE and versus_field > 0:
            strengths.append((advantage, note))
        elif advantage <= -_MIN_NORMALIZED_EDGE and versus_field < 0:
            flaws.append((abs(advantage), note.model_copy(update={"kind": "flaw"})))
    strengths.sort(key=lambda item: item[0], reverse=True)
    flaws.sort(key=lambda item: item[0], reverse=True)
    return [note for _gap, note in strengths[:_NOTE_LIMIT]] + [
        note for _gap, note in flaws[:_NOTE_LIMIT]
    ]


def _meetings(team_a_id: int, team_b_id: int, matches: list[MatchFact]) -> list[Meeting]:
    rows = []
    pair = {team_a_id, team_b_id}
    for match in matches:
        if {match.home_team_id, match.away_team_id} != pair:
            continue
        home_is_a = is_home(match, team_a_id)
        penalty = None
        if match.home_penalty_score is not None and match.away_penalty_score is not None:
            a_pens = match.home_penalty_score if home_is_a else match.away_penalty_score
            b_pens = match.away_penalty_score if home_is_a else match.home_penalty_score
            penalty = f"{a_pens}–{b_pens}"
        rows.append(
            Meeting(
                match_id=str(match.match_id),
                stage=match.stage_name,
                team_a_score=match.home_score if home_is_a else match.away_score,
                team_b_score=match.away_score if home_is_a else match.home_score,
                team_a_result=outcome(match, team_a_id),
                penalty_score=penalty,
            )
        )
    return rows


def _position_groups(
    team_a_id: int, team_b_id: int, players: list[PlayerFact]
) -> list[PositionGroup]:
    grouped: dict[int, dict[Position, list[ComparisonPlayer]]] = {
        team_a_id: defaultdict(list),
        team_b_id: defaultdict(list),
    }
    for player in players:
        if player.team_id not in grouped:
            continue
        position = normalize_position(player.position)
        grouped[player.team_id][position].append(_comparison_player(player, position))
    groups = []
    for position in _POSITIONS:
        a_players = _sorted_players(grouped[team_a_id][position])
        b_players = _sorted_players(grouped[team_b_id][position])
        groups.append(
            PositionGroup(
                position=position,
                team_a_players=a_players,
                team_b_players=b_players,
                team_a_rollup=_rollup(a_players),
                team_b_rollup=_rollup(b_players),
            )
        )
    return groups


def _sorted_players(players: list[ComparisonPlayer]) -> list[ComparisonPlayer]:
    return sorted(players, key=lambda player: (-player.minutes, player.name))


def _comparison_player(player: PlayerFact, position: Position) -> ComparisonPlayer:
    saves_per90 = None if player.saves is None else per_ninety(player.saves, player.minutes)
    conceded_per90 = (
        None
        if player.goals_conceded is None
        else per_ninety(player.goals_conceded, player.minutes)
    )
    return ComparisonPlayer(
        id=str(player.player_id),
        name=player.name,
        initials=player_initials(player.name),
        position=position,
        club=player.club,
        age=completed_age(player.date_of_birth, WORLD_CUP_AGE_AS_OF),
        height_cm=player.height_cm,
        market_value_eur=player.market_value_eur,
        caps=player.caps,
        appearances=player.appearances,
        starts=player.starts,
        minutes=player.minutes,
        goals=player.goals,
        assists=player.assists,
        goals_per90=per_ninety(player.goals, player.minutes),
        assists_per90=per_ninety(player.assists, player.minutes),
        goal_contributions_per90=per_ninety(player.goals + player.assists, player.minutes),
        yellow_cards=player.yellow_cards,
        red_cards=player.red_cards,
        penalty_goals=player.penalty_goals,
        own_goals=player.own_goals,
        clean_sheets=player.clean_sheets,
        saves=player.saves,
        goals_conceded=player.goals_conceded,
        saves_per90=saves_per90,
        goals_conceded_per90=conceded_per90,
    )


def _rollup(players: list[ComparisonPlayer]) -> PositionRollup:
    return PositionRollup(
        minutes=sum(player.minutes for player in players),
        market_value_eur=sum(player.market_value_eur for player in players),
        goals=sum(player.goals for player in players),
        assists=sum(player.assists for player in players),
    )
