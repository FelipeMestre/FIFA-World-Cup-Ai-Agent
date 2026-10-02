"""Builders for valid team read models carrying altered values."""

from src.domain.team_analytics.model.base import TeamMatchResult, TeamRecord
from src.domain.team_analytics.model.team_analysis import (
    StatWithFieldAverage,
    TeamAnalysis,
    TeamDiscipline,
    TeamGoalsByMatch,
)
from src.domain.team_analytics.model.team_comparison import (
    ComparedStat,
    ComparedTeam,
    GroupOutcome,
    Meeting,
    SideNote,
    SquadLeader,
    SquadProfile,
    TeamComparison,
    TeamDisciplineSummary,
    TeamRates,
)

SCOPE_LABEL = "FIFA World Cup 2026"
OPPONENT_CODE = "OPP"
OPPONENT_NAME = "Opponent Land"


def build_squad_profile(*, average_age: float, market_value_eur: int) -> SquadProfile:
    return SquadProfile(
        roster_size=26,
        average_age=average_age,
        total_market_value_eur=market_value_eur,
        youngest_age=19,
        oldest_age=36,
        under_23_pct=15.0,
        over_30_pct=20.0,
        top_three_value_share_pct=40.0,
        distinct_starters=15,
        starter_minutes_share_pct=70.0,
        transfermarkt_average_age=None,
        transfermarkt_market_value_eur=None,
        transfermarkt_squad_size=None,
    )


def build_squad_leader(name: str, goals: int) -> SquadLeader:
    return SquadLeader(
        player_id="900001",
        name=name,
        position="FWD",
        goals=goals,
        assists=2,
        minutes=630,
    )


def _record_from(won: int, drawn: int, lost: int, goals_for: int, goals_against: int) -> TeamRecord:
    return TeamRecord(
        won=won, drawn=drawn, lost=lost, goals_for=goals_for, goals_against=goals_against
    )


def build_team_analysis(
    *,
    name: str,
    code: str,
    standing_label: str,
    won: int,
    lost: int,
    goals_for: int,
    manager_name: str,
    top_scorer_name: str,
    top_scorer_goals: int,
    fifa_ranking: int,
    group_points: int = 7,
) -> TeamAnalysis:
    """A `TeamAnalysis` that states the altered record in every place the model
    reads it: standing label, record, goal difference, results and leaders.
    """
    goals_against = 3
    return TeamAnalysis(
        id="800001",
        code=code,
        name=name,
        scope_label=SCOPE_LABEL,
        standing_label=standing_label,
        record=_record_from(won, 0, lost, goals_for, goals_against),
        goal_difference=goals_for - goals_against,
        conceded_per_game=round(goals_against / (won + lost), 2),
        clean_sheets=1,
        avg_possession_pct=52.0,
        goals_by_match=[
            TeamGoalsByMatch(opponent_code=OPPONENT_CODE, goals_for=goals_for, goals_against=0)
        ],
        tournament_averages=[
            StatWithFieldAverage(
                label="Goals per game", value="2.1", field_value="1.4", delta="▲ 0.7"
            )
        ],
        match_results=[
            TeamMatchResult(
                stage="Group Stage",
                opponent_code=OPPONENT_CODE,
                opponent_name=OPPONENT_NAME,
                score=f"{goals_for}-0",
                result="W",
            )
        ],
        discipline=TeamDiscipline(
            yellow_cards=4, red_cards=0, fouls=60, yellow_per_match=1.0, field_yellow_per_match=1.5
        ),
        stage_caption="Group Stage",
        confederation="CONMEBOL",
        group_letter="C",
        manager_name=manager_name,
        fifa_ranking_pre_tournament=fifa_ranking,
        squad=build_squad_profile(average_age=27.4, market_value_eur=600_000_000),
        group=GroupOutcome(
            played=3, points=group_points, goal_difference=goals_for - goals_against
        ),
        top_scorer=build_squad_leader(top_scorer_name, top_scorer_goals),
        top_assister=None,
        most_minutes=None,
        positions=[],
    )


def _team_rates(goals_per_game: float) -> TeamRates:
    return TeamRates(
        goals_per_game=goals_per_game,
        conceded_per_game=1.0,
        xg_for=8.0,
        xg_against=5.0,
        xg_difference=3.0,
        xg_per_game=1.6,
        xg_against_per_game=1.0,
        possession_pct=50.0,
        shots_per_game=12.0,
        shots_on_target_per_game=5.0,
        shot_accuracy_pct=41.0,
        conversion_pct=11.0,
        corners_per_game=5.0,
        fouls_per_game=12.0,
        offsides_per_game=2.0,
        saves=10,
        saves_per_game=2.0,
        clean_sheets=1,
        clean_sheets_per_game=0.2,
    )


def build_compared_team(
    *, name: str, code: str, won: int, lost: int, goals_per_game: float, market_value_eur: int
) -> ComparedTeam:
    return ComparedTeam(
        id=f"80000{won}",
        code=code,
        name=name,
        confederation="UEFA",
        group_letter="A",
        manager_name=None,
        fifa_ranking_pre_tournament=None,
        elo_rating=None,
        standing_label=f"{won} wins, {lost} losses",
        stage_caption="Group Stage",
        record=_record_from(won, 0, lost, won * 2, lost * 2),
        goal_difference=won * 2 - lost * 2,
        rates=_team_rates(goals_per_game),
        discipline=TeamDisciplineSummary(
            yellow_cards=4, red_cards=0, fouls=60, yellow_per_match=1.0
        ),
        squad=build_squad_profile(average_age=27.0, market_value_eur=market_value_eur),
        group=GroupOutcome(played=won + lost, points=won * 3, goal_difference=0),
        match_results=[],
        top_scorer=None,
        top_assister=None,
        most_minutes=None,
    )


def build_team_comparison(
    *,
    team_a: ComparedTeam,
    team_b: ComparedTeam,
    goals_a: float,
    goals_b: float,
    strength_note: str,
    meetings: list[Meeting] | None = None,
) -> TeamComparison:
    """A `TeamComparison` where `goals_a`/`goals_b` decide the goals-per-game
    row and `strength_note` is the single strength the model can cite.
    """
    return TeamComparison(
        id="cmp-800001-800002",
        scope_label=SCOPE_LABEL,
        team_a=team_a,
        team_b=team_b,
        compared_stats=[
            ComparedStat(
                label="Goals per game",
                team_a_display=f"{goals_a:.1f}",
                team_b_display=f"{goals_b:.1f}",
                field_display="1.4",
                team_a_value=goals_a,
                team_b_value=goals_b,
                field_value=1.4,
                higher_is_better=True,
                team_a_is_better=goals_a > goals_b,
                team_b_is_better=goals_b > goals_a,
            )
        ],
        strengths_and_flaws=[
            SideNote(
                side="a" if goals_a > goals_b else "b",
                kind="strength",
                label="Goals per game",
                detail=strength_note,
            )
        ],
        meetings=meetings or [],
        positions=[],
    )
