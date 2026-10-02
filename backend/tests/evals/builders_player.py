"""Builders for valid player read models carrying altered values."""

from src.domain.player_analytics.model.player_analysis import (
    PlayerAnalysis,
    PlayerBenchmarkRow,
    PlayerStatRow,
    StatChip,
)
from src.domain.player_analytics.model.player_comparison import (
    ComparisonPlayerRef,
    ComparisonRowData,
    PlayerComparison,
)
from src.domain.player_analytics.model.player_ranking import PlayerRanking, PlayerRankingRow

WORLD_CUP_SCOPE_LABEL = "FIFA World Cup 2026"


def _initials(name: str) -> str:
    return "".join(part[0] for part in name.split()).upper()


def build_player_analysis(
    *,
    name: str,
    team_code: str,
    goals: int,
    position: str = "FWD",
    tier_label: str = "Core contributor",
    discipline_label: str = "Clean record",
) -> PlayerAnalysis:
    """A complete, valid `PlayerAnalysis` whose goal count appears in both the
    summary chips and the full breakdown, the two places the model reads it.
    """
    return PlayerAnalysis(
        id="900001",
        name=name,
        initials=_initials(name),
        team_code=team_code,
        position=position,
        appearances=7,
        minutes=630,
        scope_label=WORLD_CUP_SCOPE_LABEL,
        tier_label=tier_label,
        tier_segments=3,
        discipline_label=discipline_label,
        chips=[
            StatChip(label="Goals", value=str(goals)),
            StatChip(label="Appearances", value="7"),
        ],
        footer_caption="Percentiles are against players at the same position.",
        full_breakdown=[
            PlayerStatRow(stat="Goals", total=str(goals), per_ninety="", percentile=99),
            PlayerStatRow(stat="Minutes", total="630", per_ninety="", percentile=None),
        ],
        per_ninety_vs_position_average=[
            PlayerBenchmarkRow(label="Goals", value=round(goals / 7, 2), position_average=0.3),
        ],
    )


def _comparison_player(name: str, team_code: str, id_: str) -> ComparisonPlayerRef:
    return ComparisonPlayerRef(
        id=id_,
        initials=_initials(name),
        name=name,
        team_code=team_code,
        position="FWD",
        minutes=630,
    )


def build_player_comparison(
    *,
    player_a: str,
    team_a_code: str,
    goals_a: int,
    player_b: str,
    team_b_code: str,
    goals_b: int,
    insight: str,
) -> PlayerComparison:
    """A `PlayerComparison` whose goal totals decide which player is better,
    with the headline insight (the model's main talking point) set by the test.
    """
    goals_row = ComparisonRowData(
        label="Goals",
        player_a_per_ninety=f"{goals_a / 7:.2f}",
        player_b_per_ninety=f"{goals_b / 7:.2f}",
        player_a_total=str(goals_a),
        player_b_total=str(goals_b),
        player_a_is_better=goals_a > goals_b,
        player_b_is_better=goals_b > goals_a,
        player_a_total_is_better=goals_a > goals_b,
        player_b_total_is_better=goals_b > goals_a,
        player_a_percentile=95 if goals_a > goals_b else 40,
        player_b_percentile=95 if goals_b > goals_a else 40,
    )
    return PlayerComparison(
        id="cmp-900001-900002",
        normalization="per90",
        scope_label=WORLD_CUP_SCOPE_LABEL,
        player_a=_comparison_player(player_a, team_a_code, "900001"),
        player_b=_comparison_player(player_b, team_b_code, "900002"),
        rows=[goals_row],
        insights=[insight],
        min_minutes_caption="Players need at least 90 minutes to be compared.",
    )


def build_ranking_row(
    *, rank: int, name: str, team_code: str, goals: int, position: str = "FWD"
) -> PlayerRankingRow:
    return PlayerRankingRow(
        rank=rank,
        player_id=str(900000 + rank),
        name=name,
        initials=_initials(name),
        team_code=team_code,
        club_team="Altered FC",
        position=position,
        value=str(goals),
        sort_value=float(goals),
        appearances=7,
        minutes=630,
        goals=goals,
        assists=1,
        yellow_cards=0,
        red_cards=0,
        height_cm=180,
        age=27,
    )


def build_goals_ranking(rows: list[PlayerRankingRow]) -> PlayerRanking:
    """A world-cup goals ranking over the given rows, in the given order."""
    return PlayerRanking(
        id="ranking-goals",
        scope="world_cup",
        rank_by="goals",
        rank_by_label="Goals",
        scope_label=WORLD_CUP_SCOPE_LABEL,
        footer_caption="World Cup 2026 tournament stats only.",
        rows=rows,
    )
