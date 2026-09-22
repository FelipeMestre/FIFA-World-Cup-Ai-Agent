"""SQL-first aggregation for the `get_player_analysis` chat tool.

Known data-quality gaps in the source dataset (see `PlayerStatSchema`'s own
docstring): `shots`/`shots_on_target`/`average_rating` are always null
upstream, and `clean_sheets`/`saves`/`goals_conceded` are only populated for
goalkeepers. Both gaps are surfaced here as missing values (a chip showing
"—", a skipped breakdown row) rather than fabricated zeros -- a null means
"not measured", not "zero".

`player`/`player_stat.position` stores an abbreviated code (`"FW"`, `"DF"`,
`"MF"`, `"GK"`, confirmed against this codebase's own integration-test
fixtures) rather than the frontend's `GK`/`DEF`/`MID`/`FWD` literals, so
`_normalize_position` maps by first letter rather than an exact lookup --
tolerant of an upstream `"Defender"`/`"Forward"`-style spelling too, since
nothing elsewhere in the codebase pins the exact upstream spelling down.
"""

from typing import Annotated, Literal

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.player_analytics.model.player_analysis import (
    PlayerAnalysis,
    PlayerBenchmarkRow,
    PlayerStatRow,
    StatChip,
)
from src.infra.postgres.config import get_db
from src.infra.postgres.interfaces.player_analytics_repository_interface import (
    PlayerAnalyticsRepositoryInterface,
)
from src.infra.postgres.schemas.national_team_schema import NationalTeamSchema
from src.infra.postgres.schemas.player_schema import PlayerSchema, PlayerStatSchema

Position = Literal["GK", "DEF", "MID", "FWD"]

_POSITION_BY_FIRST_LETTER: dict[str, Position] = {
    "G": "GK",
    "D": "DEF",
    "M": "MID",
    "F": "FWD",
}
_FIRST_LETTER_BY_POSITION: dict[Position, str] = {
    letter_position: letter for letter, letter_position in _POSITION_BY_FIRST_LETTER.items()
}

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


class _SqlAlchemyPlayerAnalyticsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_player_analysis(self, player_query: str) -> PlayerAnalysis | None:
        player_row = await self._resolve_player(player_query)
        if player_row is None:
            return None

        stat_row = await self._get_player_stat(player_row.player_id)
        if stat_row is None:
            return None

        position = _normalize_position(stat_row.position or player_row.position)
        team_code = await self._get_team_code(player_row.team_id)
        peer_rows = await self._get_position_peers(position)

        is_gk = position == "GK"
        primary_percentile = _primary_contribution_percentile(stat_row, peer_rows, is_gk)
        tier_label, tier_segments = _tier_for_percentile(primary_percentile)

        return PlayerAnalysis(
            id=str(player_row.player_id),
            name=player_row.player_name,
            initials=_initials(player_row.player_name),
            team_code=team_code,
            position=position,
            appearances=stat_row.matches_played,
            minutes=stat_row.minutes_played,
            scope_label=f"WC 2026 · {stat_row.matches_played} apps",
            tier_label=tier_label,
            tier_segments=tier_segments,
            discipline_label=_discipline_label(stat_row),
            chips=_build_chips(stat_row, is_gk),
            footer_caption=(
                f"{stat_row.matches_played} apps · {stat_row.minutes_played} min · "
                f"verified {stat_row.last_verified.isoformat()}"
            ),
            full_breakdown=_build_full_breakdown(stat_row, peer_rows, is_gk),
            per_ninety_vs_position_average=_build_benchmarks(stat_row, peer_rows, is_gk),
        )

    async def _resolve_player(self, player_query: str) -> PlayerSchema | None:
        exact_stmt = select(PlayerSchema).where(PlayerSchema.player_name.ilike(player_query))
        exact_match = (await self._session.execute(exact_stmt)).scalars().first()
        if exact_match is not None:
            return exact_match

        fuzzy_stmt = (
            select(PlayerSchema)
            .where(PlayerSchema.player_name.ilike(f"%{player_query}%"))
            .limit(1)
        )
        return (await self._session.execute(fuzzy_stmt)).scalars().first()

    async def _get_player_stat(self, player_id: int) -> PlayerStatSchema | None:
        return await self._session.get(PlayerStatSchema, player_id)

    async def _get_team_code(self, team_id: int) -> str:
        team_row = await self._session.get(NationalTeamSchema, team_id)
        if team_row is None:
            return "???"
        return team_row.fifa_code or team_row.team_name[:3].upper()

    async def _get_position_peers(self, position: Position) -> list[PlayerStatSchema]:
        # Filters by first letter in SQL rather than fetching every row and
        # re-running `_normalize_position` in Python. Every real position
        # code in this schema starts with G/D/M/F, so this drops only
        # `_normalize_position`'s garbage-input fallback (unrecognized
        # letter -> MID), which never fires on real data.
        letter = _FIRST_LETTER_BY_POSITION[position]
        stmt = select(PlayerStatSchema).where(
            PlayerStatSchema.minutes_played > 0,
            PlayerStatSchema.position.ilike(f"{letter}%"),
        )
        return (await self._session.execute(stmt)).scalars().all()


def _normalize_position(raw_position: str) -> Position:
    first_letter = raw_position.strip()[:1].upper()
    return _POSITION_BY_FIRST_LETTER.get(first_letter, "MID")


def _initials(name: str) -> str:
    parts = [p for p in name.split() if p]
    if not parts:
        return "??"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _per_ninety(total: int, minutes_played: int) -> float:
    if minutes_played <= 0:
        return 0.0
    return round(total * 90 / minutes_played, 2)


def _percentile(value: float, population: list[float]) -> int:
    """Midpoint percentile rank of `value` within `population` (which
    includes the player's own value): the share of the population strictly
    below `value`, plus half the share exactly equal to it, as a 0-100
    integer. Returns 0 for an empty population rather than dividing by zero.
    """
    if not population:
        return 0
    below = sum(1 for v in population if v < value)
    equal = sum(1 for v in population if v == value)
    rank = (below + 0.5 * equal) / len(population) * 100
    return round(rank)


def _goal_contribution_per90(row: PlayerStatSchema) -> float:
    return _per_ninety(row.goals + row.assists, row.minutes_played)


def _saves_per90(row: PlayerStatSchema) -> float:
    return _per_ninety(row.saves or 0, row.minutes_played)


def _primary_contribution_percentile(
    stat_row: PlayerStatSchema, peer_rows: list[PlayerStatSchema], is_gk: bool
) -> int:
    metric_fn = _saves_per90 if is_gk else _goal_contribution_per90
    population = [metric_fn(row) for row in peer_rows]
    return _percentile(metric_fn(stat_row), population)


def _tier_for_percentile(percentile: int) -> tuple[str, int]:
    for threshold, label, segments in _TIER_LABELS:
        if percentile >= threshold:
            return label, segments
    return _TIER_LABEL_FALLBACK


def _discipline_label(stat_row: PlayerStatSchema) -> str:
    if stat_row.red_cards > 0:
        return "Disciplinary risk"
    if stat_row.yellow_cards >= _DISCIPLINE_CARD_PRONE_YELLOW_THRESHOLD:
        return "Card-prone"
    return "Clean record"


def _chip_value(total: int | None) -> str:
    return str(total) if total is not None else "—"


def _build_chips(stat_row: PlayerStatSchema, is_gk: bool) -> list[StatChip]:
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
        percentile=_percentile(per90, population),
    )


def _build_full_breakdown(
    stat_row: PlayerStatSchema, peer_rows: list[PlayerStatSchema], is_gk: bool
) -> list[PlayerStatRow]:
    rows: list[PlayerStatRow] = []

    if is_gk:
        rows.append(
            _breakdown_row("Saves", stat_row.saves or 0, stat_row, peer_rows, _saves_per90)
        )
        if stat_row.goals_conceded is not None:
            rows.append(
                _breakdown_row(
                    "Goals conceded",
                    stat_row.goals_conceded,
                    stat_row,
                    peer_rows,
                    lambda r: _per_ninety(r.goals_conceded or 0, r.minutes_played),
                )
            )
        if stat_row.clean_sheets is not None:
            rows.append(
                PlayerStatRow(
                    stat="Clean sheets",
                    total=str(stat_row.clean_sheets),
                    per_ninety=f"{_per_ninety(stat_row.clean_sheets, stat_row.minutes_played):.2f}",
                    percentile=_percentile(
                        _per_ninety(stat_row.clean_sheets, stat_row.minutes_played),
                        [_per_ninety(r.clean_sheets or 0, r.minutes_played) for r in peer_rows],
                    ),
                )
            )
    else:
        rows.append(_breakdown_row("Goals", stat_row.goals, stat_row, peer_rows, _goal_per90))
        rows.append(
            _breakdown_row("Assists", stat_row.assists, stat_row, peer_rows, _assist_per90)
        )
        if stat_row.shots is not None:
            rows.append(
                _breakdown_row(
                    "Shots",
                    stat_row.shots,
                    stat_row,
                    peer_rows,
                    lambda r: _per_ninety(r.shots or 0, r.minutes_played),
                )
            )

    rows.append(
        _breakdown_row(
            "Yellow cards",
            stat_row.yellow_cards,
            stat_row,
            peer_rows,
            lambda r: _per_ninety(r.yellow_cards, r.minutes_played),
        )
    )
    if stat_row.red_cards > 0 or any(r.red_cards > 0 for r in peer_rows):
        rows.append(
            _breakdown_row(
                "Red cards",
                stat_row.red_cards,
                stat_row,
                peer_rows,
                lambda r: _per_ninety(r.red_cards, r.minutes_played),
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


def _goal_per90(row: PlayerStatSchema) -> float:
    return _per_ninety(row.goals, row.minutes_played)


def _assist_per90(row: PlayerStatSchema) -> float:
    return _per_ninety(row.assists, row.minutes_played)


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 2) if values else 0.0


def _build_benchmarks(
    stat_row: PlayerStatSchema, peer_rows: list[PlayerStatSchema], is_gk: bool
) -> list[PlayerBenchmarkRow]:
    specs: list[tuple[str, object]]
    if is_gk:
        specs = [
            ("Saves per 90", _saves_per90),
            (
                "Conceded per 90",
                lambda r: _per_ninety(r.goals_conceded or 0, r.minutes_played),
            ),
        ]
    else:
        specs = [
            ("Goals per 90", _goal_per90),
            ("Assists per 90", _assist_per90),
            ("G+A per 90", _goal_contribution_per90),
        ]
        if stat_row.shots is not None:
            specs.append(("Shots per 90", lambda r: _per_ninety(r.shots or 0, r.minutes_played)))

    rows = []
    for label, metric_fn in specs:
        rows.append(
            PlayerBenchmarkRow(
                label=label,
                value=metric_fn(stat_row),
                position_average=_avg([metric_fn(row) for row in peer_rows]),
            )
        )
    return rows


def get_player_analytics_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PlayerAnalyticsRepositoryInterface:
    return _SqlAlchemyPlayerAnalyticsRepository(session)
