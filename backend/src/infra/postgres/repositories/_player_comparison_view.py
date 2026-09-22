"""Row/ref/insight builders for `get_player_comparison`, mirroring
`_player_analysis_view.py`'s split out of `player_analytics_repository.py`
(see that module's docstring for why). `_SqlAlchemyPlayerAnalyticsRepository.
get_player_comparison` calls straight into this module once it has resolved
both players' rows, stat rows, positions, and position peer rows.

Each metric spec's `is_available` guards the same "missing means unmeasured,
not zero" rule `_player_analysis_view.py` follows for a single player: a
goalkeeper-only stat (saves/conceded/clean sheets) is only included when
*both* players have it recorded, so the table never implies a 0 that was
never actually measured for an outfield player.
"""

from collections.abc import Callable

from src.domain.player_analytics.model.player_comparison import (
    ComparisonPlayerRef,
    ComparisonRowData,
)
from src.infra.postgres.repositories._player_stat_helpers import (
    Position,
    assist_per90,
    clean_sheets_per90,
    conceded_per90,
    goal_contribution_per90,
    goal_per90,
    percentile,
    player_initials,
    red_cards_per90,
    saves_per90,
    yellow_cards_per90,
)
from src.infra.postgres.schemas.player_schema import PlayerSchema, PlayerStatSchema

_INSIGHT_COUNT = 3

_MetricFn = Callable[[PlayerStatSchema], float]
_AvailabilityFn = Callable[[PlayerStatSchema], bool]

# (label, per-90 metric, availability check (both players must satisfy it),
# whether a higher value is the better outcome for that metric).
_COMPARISON_METRIC_SPECS: tuple[tuple[str, _MetricFn, _AvailabilityFn, bool], ...] = (
    ("Goals per 90", goal_per90, lambda r: True, True),
    ("Assists per 90", assist_per90, lambda r: True, True),
    ("G+A per 90", goal_contribution_per90, lambda r: True, True),
    ("Yellow cards per 90", yellow_cards_per90, lambda r: True, False),
    ("Red cards per 90", red_cards_per90, lambda r: True, False),
    ("Saves per 90", saves_per90, lambda r: r.saves is not None, True),
    ("Conceded per 90", conceded_per90, lambda r: r.goals_conceded is not None, False),
    ("Clean sheets per 90", clean_sheets_per90, lambda r: r.clean_sheets is not None, True),
)


def build_comparison_player_ref(
    player_row: PlayerSchema,
    stat_row: PlayerStatSchema,
    position: Position,
    team_code: str,
) -> ComparisonPlayerRef:
    return ComparisonPlayerRef(
        id=str(player_row.player_id),
        initials=player_initials(player_row.player_name),
        name=player_row.player_name,
        team_code=team_code,
        position=position,
        minutes=stat_row.minutes_played,
    )


def _comparison_row(
    label: str,
    metric_fn: _MetricFn,
    higher_is_better: bool,
    stat_a: PlayerStatSchema,
    peers_a: list[PlayerStatSchema],
    stat_b: PlayerStatSchema,
    peers_b: list[PlayerStatSchema],
) -> ComparisonRowData:
    value_a = metric_fn(stat_a)
    value_b = metric_fn(stat_b)
    a_ahead = value_a > value_b if higher_is_better else value_a < value_b
    b_ahead = value_b > value_a if higher_is_better else value_b < value_a
    return ComparisonRowData(
        label=label,
        player_a_value=f"{value_a:.2f}",
        player_b_value=f"{value_b:.2f}",
        player_a_is_better=a_ahead,
        player_b_is_better=b_ahead,
        player_a_percentile=percentile(value_a, [metric_fn(row) for row in peers_a]),
        player_b_percentile=percentile(value_b, [metric_fn(row) for row in peers_b]),
    )


def build_comparison_rows(
    stat_a: PlayerStatSchema,
    peers_a: list[PlayerStatSchema],
    stat_b: PlayerStatSchema,
    peers_b: list[PlayerStatSchema],
) -> list[ComparisonRowData]:
    rows = [
        _comparison_row(label, metric_fn, higher_is_better, stat_a, peers_a, stat_b, peers_b)
        for label, metric_fn, is_available, higher_is_better in _COMPARISON_METRIC_SPECS
        if is_available(stat_a) and is_available(stat_b)
    ]
    # Biggest percentile gap first -- the frontend has no top-N field of its
    # own (see `PlayerComparison.rows`), so the ordering itself is what
    # surfaces the most meaningful differences first; the full list is
    # still returned for the frontend to slice.
    rows.sort(
        key=lambda row: abs((row.player_a_percentile or 0) - (row.player_b_percentile or 0)),
        reverse=True,
    )
    return rows


def build_comparison_insights(name_a: str, name_b: str, rows: list[ComparisonRowData]) -> list[str]:
    insights: list[str] = []
    for row in rows[:_INSIGHT_COUNT]:
        if row.player_a_is_better:
            leader, trailer = name_a, name_b
            leader_value, trailer_value = row.player_a_value, row.player_b_value
            leader_percentile = row.player_a_percentile
        elif row.player_b_is_better:
            leader, trailer = name_b, name_a
            leader_value, trailer_value = row.player_b_value, row.player_a_value
            leader_percentile = row.player_b_percentile
        else:
            continue
        insights.append(
            f"{leader} leads {trailer} in {row.label.lower()} "
            f"({leader_value} vs {trailer_value}, {leader_percentile}th percentile)."
        )
    return insights
