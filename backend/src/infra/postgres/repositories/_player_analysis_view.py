"""Single-player breakdown builders for `get_player_analysis`, extracted out
of `player_analytics_repository.py` alongside `_player_stat_helpers.py` once
adding `get_player_comparison` pushed that file past the project's 400-line
cap (see AGENTS.md's file-size rule). `_SqlAlchemyPlayerAnalyticsRepository.
get_player_analysis` calls straight into this module once it has resolved
the player row, stat row, and position peer rows.

Known data-quality gaps in the source dataset (see `PlayerStatSchema`'s own
docstring): `shots`/`shots_on_target`/`average_rating` are always null
upstream, and `clean_sheets`/`saves`/`goals_conceded` are only populated for
goalkeepers. Both gaps are surfaced here as missing values (a chip showing
"—", a skipped breakdown row) rather than fabricated zeros -- a null means
"not measured", not "zero".
"""

from src.domain.player_analytics.model.player_analysis import (
    PlayerBenchmarkRow,
    PlayerStatRow,
    StatChip,
)
from src.infra.postgres.repositories._player_stat_helpers import (
    assist_per90,
    average,
    goal_contribution_per90,
    goal_per90,
    per_ninety,
    percentile,
    saves_per90,
)
from src.infra.postgres.schemas.player_schema import PlayerStatSchema

# Contribution-tier thresholds, expressed as a percentile (0-100) of the
# player's primary per-90 metric within their own position: goal
# contribution (goals + assists) per 90 for outfield players, saves per 90
# for goalkeepers (there is no clean "contribution" stat for a keeper
# beyond shot-stopping volume in this dataset).
_TIER_ELITE_PERCENTILE = 80
_TIER_CORE_PERCENTILE = 50
_TIER_ROTATION_PERCENTILE = 20

_TIER_LABELS: tuple[tuple[int, str, int], ...] = (
    (_TIER_ELITE_PERCENTILE, "Elite contributor", 3),
    (_TIER_CORE_PERCENTILE, "Core contributor", 2),
    (_TIER_ROTATION_PERCENTILE, "Rotational", 1),
)
_TIER_LABEL_FALLBACK = ("Limited sample", 0)

_DISCIPLINE_CARD_PRONE_YELLOW_THRESHOLD = 3


def primary_contribution_percentile(
    stat_row: PlayerStatSchema, peer_rows: list[PlayerStatSchema], is_gk: bool
) -> int:
    metric_fn = saves_per90 if is_gk else goal_contribution_per90
    population = [metric_fn(row) for row in peer_rows]
    return percentile(metric_fn(stat_row), population)


def tier_for_percentile(percentile_value: int) -> tuple[str, int]:
    for threshold, label, segments in _TIER_LABELS:
        if percentile_value >= threshold:
            return label, segments
    return _TIER_LABEL_FALLBACK


def discipline_label(stat_row: PlayerStatSchema) -> str:
    if stat_row.red_cards > 0:
        return "Disciplinary risk"
    if stat_row.yellow_cards >= _DISCIPLINE_CARD_PRONE_YELLOW_THRESHOLD:
        return "Card-prone"
    return "Clean record"


def _chip_value(total: int | None) -> str:
    return str(total) if total is not None else "—"


def build_chips(stat_row: PlayerStatSchema, is_gk: bool) -> list[StatChip]:
    if is_gk:
        return [
            StatChip(label="Saves", value=_chip_value(stat_row.saves)),
            StatChip(label="Clean sheets", value=_chip_value(stat_row.clean_sheets)),
            StatChip(label="Conceded", value=_chip_value(stat_row.goals_conceded)),
            StatChip(label="Minutes", value=str(stat_row.minutes_played)),
        ]
    return [
        StatChip(label="Goals", value=_chip_value(stat_row.goals)),
        StatChip(label="Assists", value=_chip_value(stat_row.assists)),
        StatChip(label="Shots", value=_chip_value(stat_row.shots)),
        StatChip(label="Minutes", value=str(stat_row.minutes_played)),
    ]


def _breakdown_row(
    label: str,
    total: int,
    stat_row: PlayerStatSchema,
    peer_rows: list[PlayerStatSchema],
    metric_fn,
) -> PlayerStatRow:
    per90 = metric_fn(stat_row)
    population = [metric_fn(row) for row in peer_rows]
    return PlayerStatRow(
        stat=label,
        total=str(total),
        per_ninety=f"{per90:.2f}",
        percentile=percentile(per90, population),
    )


def build_full_breakdown(
    stat_row: PlayerStatSchema, peer_rows: list[PlayerStatSchema], is_gk: bool
) -> list[PlayerStatRow]:
    rows: list[PlayerStatRow] = []

    if is_gk:
        rows.append(_breakdown_row("Saves", stat_row.saves or 0, stat_row, peer_rows, saves_per90))
        if stat_row.goals_conceded is not None:
            rows.append(
                _breakdown_row(
                    "Goals conceded",
                    stat_row.goals_conceded,
                    stat_row,
                    peer_rows,
                    lambda r: per_ninety(r.goals_conceded or 0, r.minutes_played),
                )
            )
        if stat_row.clean_sheets is not None:
            rows.append(
                PlayerStatRow(
                    stat="Clean sheets",
                    total=str(stat_row.clean_sheets),
                    per_ninety=f"{per_ninety(stat_row.clean_sheets, stat_row.minutes_played):.2f}",
                    percentile=percentile(
                        per_ninety(stat_row.clean_sheets, stat_row.minutes_played),
                        [per_ninety(r.clean_sheets or 0, r.minutes_played) for r in peer_rows],
                    ),
                )
            )
    else:
        rows.append(_breakdown_row("Goals", stat_row.goals, stat_row, peer_rows, goal_per90))
        rows.append(_breakdown_row("Assists", stat_row.assists, stat_row, peer_rows, assist_per90))
        if stat_row.shots is not None:
            rows.append(
                _breakdown_row(
                    "Shots",
                    stat_row.shots,
                    stat_row,
                    peer_rows,
                    lambda r: per_ninety(r.shots or 0, r.minutes_played),
                )
            )

    rows.append(
        _breakdown_row(
            "Yellow cards",
            stat_row.yellow_cards,
            stat_row,
            peer_rows,
            lambda r: per_ninety(r.yellow_cards, r.minutes_played),
        )
    )
    if stat_row.red_cards > 0 or any(r.red_cards > 0 for r in peer_rows):
        rows.append(
            _breakdown_row(
                "Red cards",
                stat_row.red_cards,
                stat_row,
                peer_rows,
                lambda r: per_ninety(r.red_cards, r.minutes_played),
            )
        )

    # Minutes carries no percentile -- it is playing time, not a
    # performance stat to be ranked against peers (frontend's
    # `PlayerStatRow.percentile` is explicitly optional for this reason).
    rows.append(
        PlayerStatRow(
            stat="Minutes",
            total=str(stat_row.minutes_played),
            per_ninety="90.00" if stat_row.minutes_played > 0 else "0.00",
            percentile=None,
        )
    )
    return rows


def build_benchmarks(
    stat_row: PlayerStatSchema, peer_rows: list[PlayerStatSchema], is_gk: bool
) -> list[PlayerBenchmarkRow]:
    specs: list[tuple[str, object]]
    if is_gk:
        specs = [
            ("Saves per 90", saves_per90),
            ("Conceded per 90", lambda r: per_ninety(r.goals_conceded or 0, r.minutes_played)),
        ]
    else:
        specs = [
            ("Goals per 90", goal_per90),
            ("Assists per 90", assist_per90),
            ("G+A per 90", goal_contribution_per90),
        ]
        if stat_row.shots is not None:
            specs.append(("Shots per 90", lambda r: per_ninety(r.shots or 0, r.minutes_played)))

    rows = []
    for label, metric_fn in specs:
        rows.append(
            PlayerBenchmarkRow(
                label=label,
                value=metric_fn(stat_row),
                position_average=average([metric_fn(row) for row in peer_rows]),
            )
        )
    return rows
