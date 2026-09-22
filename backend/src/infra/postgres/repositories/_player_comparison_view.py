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
_TotalFn = Callable[[PlayerStatSchema], int]
_AvailabilityFn = Callable[[PlayerStatSchema], bool]

# (label, per-90 metric, raw total (pre per-90 division -- see `per_ninety`
# in `_player_stat_helpers.py`), availability check (both players must
# satisfy it), whether a higher value is the better outcome for that metric).
_COMPARISON_METRIC_SPECS: tuple[tuple[str, _MetricFn, _TotalFn, _AvailabilityFn, bool], ...] = (
    ("Goals per 90", goal_per90, lambda r: r.goals, lambda r: True, True),
    ("Assists per 90", assist_per90, lambda r: r.assists, lambda r: True, True),
    (
        "G+A per 90",
        goal_contribution_per90,
        lambda r: r.goals + r.assists,
        lambda r: True,
        True,
    ),
    ("Yellow cards per 90", yellow_cards_per90, lambda r: r.yellow_cards, lambda r: True, False),
    ("Red cards per 90", red_cards_per90, lambda r: r.red_cards, lambda r: True, False),
    (
        "Saves per 90",
        saves_per90,
        lambda r: r.saves or 0,
        lambda r: r.saves is not None,
        True,
    ),
    (
        "Conceded per 90",
        conceded_per90,
        lambda r: r.goals_conceded or 0,
        lambda r: r.goals_conceded is not None,
        False,
    ),
    (
        "Clean sheets per 90",
        clean_sheets_per90,
        lambda r: r.clean_sheets or 0,
        lambda r: r.clean_sheets is not None,
        True,
    ),
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
    total_fn: _TotalFn,
    higher_is_better: bool,
    stat_a: PlayerStatSchema,
    peers_a: list[PlayerStatSchema],
    stat_b: PlayerStatSchema,
    peers_b: list[PlayerStatSchema],
) -> ComparisonRowData:
    per_ninety_a = metric_fn(stat_a)
    per_ninety_b = metric_fn(stat_b)
    total_a = total_fn(stat_a)
    total_b = total_fn(stat_b)
    per_ninety_a_ahead = (
        per_ninety_a > per_ninety_b if higher_is_better else per_ninety_a < per_ninety_b
    )
    per_ninety_b_ahead = (
        per_ninety_b > per_ninety_a if higher_is_better else per_ninety_b < per_ninety_a
    )
    total_a_ahead = total_a > total_b if higher_is_better else total_a < total_b
    total_b_ahead = total_b > total_a if higher_is_better else total_b < total_a
    return ComparisonRowData(
        label=label,
        player_a_per_ninety=f"{per_ninety_a:.2f}",
        player_b_per_ninety=f"{per_ninety_b:.2f}",
        player_a_total=str(total_a),
        player_b_total=str(total_b),
        player_a_is_better=per_ninety_a_ahead,
        player_b_is_better=per_ninety_b_ahead,
        player_a_total_is_better=total_a_ahead,
        player_b_total_is_better=total_b_ahead,
        player_a_percentile=percentile(per_ninety_a, [metric_fn(row) for row in peers_a]),
        player_b_percentile=percentile(per_ninety_b, [metric_fn(row) for row in peers_b]),
    )


def build_comparison_rows(
    stat_a: PlayerStatSchema,
    peers_a: list[PlayerStatSchema],
    stat_b: PlayerStatSchema,
    peers_b: list[PlayerStatSchema],
) -> list[ComparisonRowData]:
    rows = [
        _comparison_row(
            label, metric_fn, total_fn, higher_is_better, stat_a, peers_a, stat_b, peers_b
        )
        for label, metric_fn, total_fn, is_available, higher_is_better in _COMPARISON_METRIC_SPECS
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
            leader_value, trailer_value = row.player_a_per_ninety, row.player_b_per_ninety
            leader_percentile = row.player_a_percentile
        elif row.player_b_is_better:
            leader, trailer = name_b, name_a
            leader_value, trailer_value = row.player_b_per_ninety, row.player_a_per_ninety
            leader_percentile = row.player_b_percentile
        else:
            continue
        insights.append(
            f"{leader} leads {trailer} in {row.label.lower()} "
            f"({leader_value} vs {trailer_value}, {leader_percentile}th percentile)."
        )
    return insights
