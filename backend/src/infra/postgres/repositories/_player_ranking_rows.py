"""Hydrate `query_player_stats` SQL rows into the ranking widget model."""

import hashlib
import json
from typing import Any

from src.domain.player_analytics.model.player_ranking import (
    FIELD_LABELS,
    PER90_FIELDS,
    PlayerRanking,
    PlayerRankingRow,
    PlayerStatField,
    QueryDataset,
    QueryPlayerStatsRequest,
    SeasonWindow,
    widget_scope,
)
from src.infra.postgres.repositories._player_stat_helpers import (
    normalize_position,
    player_initials,
)


def _format_value(field: PlayerStatField, sort_value: float) -> str:
    if field in PER90_FIELDS:
        return f"{sort_value:.2f}"
    if sort_value.is_integer():
        return str(int(sort_value))
    return f"{sort_value:.2f}"


def _ranking_id(request: QueryPlayerStatsRequest) -> str:
    payload = {
        "dataset": request.dataset,
        "sort_by": request.sort_by,
        "sort_dir": request.sort_dir,
        "filters": [
            {"field": item.field, "op": item.op, "value": item.value} for item in request.filters
        ],
        "season_window": request.season_window,
        "competition_id": request.competition_id,
        "limit": request.limit,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    return digest[:16]


def _scope_label(request: QueryPlayerStatsRequest) -> str:
    criterion = FIELD_LABELS[request.sort_by]
    if request.dataset == QueryDataset.WORLD_CUP:
        return f"WC 2026 · {criterion}"
    window = "latest season" if request.season_window == SeasonWindow.LATEST else "last 3 seasons"
    return f"Club · {window} · {request.competition_label}"


def _display_value(request: QueryPlayerStatsRequest, raw: Any, sort_value: float) -> str:
    if request.sort_by == PlayerStatField.POSITION:
        return normalize_position(raw.position)
    if request.sort_by == PlayerStatField.NATIONALITY:
        return str(raw.team_code)
    if request.sort_by == PlayerStatField.HEIGHT_CM:
        return f"{int(sort_value)} cm"
    return _format_value(request.sort_by, sort_value)


def _as_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    return int(value)


def _as_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _coerce_sort_value(raw_value: Any) -> float:
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return 0.0


def _build_ranking(request: QueryPlayerStatsRequest, raw_rows: list[Any]) -> PlayerRanking:
    rows: list[PlayerRankingRow] = []
    for index, raw in enumerate(raw_rows, start=1):
        sort_value = round(_coerce_sort_value(raw.sort_value), 2)
        rows.append(
            PlayerRankingRow(
                rank=index,
                player_id=str(raw.player_id),
                name=raw.player_name,
                initials=player_initials(raw.player_name),
                team_code=raw.team_code,
                club_team=raw.club_team,
                position=normalize_position(raw.position),
                value=_display_value(request, raw, sort_value),
                sort_value=sort_value,
                appearances=_as_int(raw.appearances),
                minutes=_as_int(raw.minutes),
                goals=_as_int(getattr(raw, "goals", None)),
                assists=_as_int(getattr(raw, "assists", None)),
                yellow_cards=_as_int(getattr(raw, "yellow_cards", None)),
                red_cards=_as_int(getattr(raw, "red_cards", None)),
                height_cm=_as_int(raw.height_cm),
                age=_as_int(raw.age),
                starts=_as_optional_int(getattr(raw, "starts", None)),
                penalty_goals=_as_optional_int(getattr(raw, "penalty_goals", None)),
                saves=_as_optional_int(getattr(raw, "saves", None)),
                clean_sheets=_as_optional_int(getattr(raw, "clean_sheets", None)),
                goals_conceded=_as_optional_int(getattr(raw, "goals_conceded", None)),
            )
        )
    linked_note = (
        "approved Transfermarkt links only"
        if request.dataset == QueryDataset.CLUB_SEASONS
        else "tournament stats"
    )
    return PlayerRanking(
        id=_ranking_id(request),
        scope=widget_scope(request.dataset),
        rank_by=request.sort_by.value,
        rank_by_label=FIELD_LABELS[request.sort_by],
        scope_label=_scope_label(request),
        footer_caption=f"{len(rows)} players · {linked_note}",
        rows=rows,
    )
