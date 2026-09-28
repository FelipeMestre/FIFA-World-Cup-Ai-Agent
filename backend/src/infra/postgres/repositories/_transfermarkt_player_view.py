"""Career-totals breakdown builder for `get_player_analysis`'s
Transfermarkt fallback path -- a player with no World Cup `player`/
`player_stat` row, resolved via `real_player`/`real_player_season_stat`
instead (see `player_analytics_repository.py`'s
`_build_transfermarkt_fallback_analysis`).

No World Cup peer population exists for a Transfermarkt-only player, so
every `PlayerStatRow.percentile` here is `None` and no per-90-vs-position
benchmark is produced at all (`PlayerAnalysis.per_ninety_vs_position_average`
stays `[]`) -- confirmed design decision, see
`odd/tasks/player-analysis-transfermarkt-fallback.md`.
"""

from src.domain.player_analytics.model.player_analysis import (
    PlayerSeasonStat,
    PlayerStatRow,
    StatChip,
)
from src.infra.postgres.repositories._player_stat_helpers import per_ninety

# Same threshold `_player_analysis_view.discipline_label` uses for the World
# Cup path, applied here to summed career totals instead of a single
# tournament's count.
_CARD_PRONE_YELLOW_THRESHOLD = 3


def _sum_field(seasons: list[PlayerSeasonStat], field: str) -> int:
    return sum(getattr(season, field) for season in seasons)


def total_minutes(seasons: list[PlayerSeasonStat]) -> int:
    return _sum_field(seasons, "minutes")


def total_appearances(seasons: list[PlayerSeasonStat]) -> int:
    return _sum_field(seasons, "appearances")


def _totals_row(label: str, total: int, minutes: int) -> PlayerStatRow:
    return PlayerStatRow(
        stat=label,
        total=str(total),
        per_ninety=f"{per_ninety(total, minutes):.2f}",
        percentile=None,
    )


def build_full_breakdown(seasons: list[PlayerSeasonStat]) -> list[PlayerStatRow]:
    minutes = total_minutes(seasons)
    rows = [
        _totals_row("Appearances", total_appearances(seasons), minutes),
        _totals_row("Goals", _sum_field(seasons, "goals"), minutes),
        _totals_row("Assists", _sum_field(seasons, "assists"), minutes),
        _totals_row("Yellow cards", _sum_field(seasons, "yellow_cards"), minutes),
        _totals_row("Red cards", _sum_field(seasons, "red_cards"), minutes),
    ]
    # Minutes carries no percentile -- it is playing time, not a performance
    # stat to be ranked (mirrors `_player_analysis_view.build_full_breakdown`).
    rows.append(
        PlayerStatRow(
            stat="Minutes",
            total=str(minutes),
            per_ninety="90.00" if minutes > 0 else "0.00",
            percentile=None,
        )
    )
    return rows


def build_chips(seasons: list[PlayerSeasonStat]) -> list[StatChip]:
    return [
        StatChip(label="Goals", value=str(_sum_field(seasons, "goals"))),
        StatChip(label="Assists", value=str(_sum_field(seasons, "assists"))),
        StatChip(label="Appearances", value=str(total_appearances(seasons))),
        StatChip(label="Minutes", value=str(total_minutes(seasons))),
    ]


def discipline_label(seasons: list[PlayerSeasonStat]) -> str:
    if _sum_field(seasons, "red_cards") > 0:
        return "Disciplinary risk"
    if _sum_field(seasons, "yellow_cards") >= _CARD_PRONE_YELLOW_THRESHOLD:
        return "Card-prone"
    return "Clean record"
