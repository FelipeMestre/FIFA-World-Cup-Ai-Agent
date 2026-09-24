"""Hydrate ranking SQL rows into the `PlayerRanking` widget model."""

import hashlib
import json
from typing import Any

from src.domain.player_analytics.model.player_ranking import (
    PER90_RANK_BY,
    RANK_BY_LABELS,
    PlayerRanking,
    PlayerRankingRequest,
    PlayerRankingRow,
    RankBy,
    RankingScope,
    SeasonWindow,
)
from src.infra.postgres.repositories._player_stat_helpers import (
    normalize_position,
    player_initials,
)


def _format_value(rank_by: RankBy, sort_value: float) -> str:
    if rank_by in PER90_RANK_BY:
        return f"{sort_value:.2f}"
    if sort_value.is_integer():
        return str(int(sort_value))
    return f"{sort_value:.2f}"


def _ranking_id(request: PlayerRankingRequest) -> str:
    payload = {
        "scope": request.scope,
        "rank_by": request.rank_by,
        "position": request.position,
        "age_min": request.age_min,
        "age_max": request.age_max,
        "height_min_cm": request.height_min_cm,
        "height_max_cm": request.height_max_cm,
        "nationality": request.nationality,
        "season_window": request.season_window,
        "competition_id": request.competition_id,
        "limit": request.limit,
        "min_appearances": request.min_appearances,
        "min_minutes": request.min_minutes,
        "min_goals": request.min_goals,
        "min_assists": request.min_assists,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return digest[:16]


def _scope_label(request: PlayerRankingRequest) -> str:
    criterion = RANK_BY_LABELS[request.rank_by]
    if request.scope == RankingScope.WORLD_CUP:
        return f"WC 2026 · {criterion}"
    window = "latest season" if request.season_window == SeasonWindow.LATEST else "last 3 seasons"
    return f"Club · {window} · {request.competition_label}"


def _as_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    return int(value)


def _as_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _build_ranking(request: PlayerRankingRequest, raw_rows: list[Any]) -> PlayerRanking:
    rows: list[PlayerRankingRow] = []
    for index, raw in enumerate(raw_rows, start=1):
        sort_value = float(raw.sort_value)
        rows.append(
            PlayerRankingRow(
                rank=index,
                player_id=str(raw.player_id),
                name=raw.player_name,
                initials=player_initials(raw.player_name),
                team_code=raw.team_code,
                club_team=raw.club_team,
                position=normalize_position(raw.position),
                value=_format_value(request.rank_by, sort_value),
                sort_value=round(sort_value, 2),
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
        if request.scope == RankingScope.TRANSFERMARKT
        else "tournament stats"
    )
    return PlayerRanking(
        id=_ranking_id(request),
        scope=request.scope.value,
        rank_by=request.rank_by.value,
        rank_by_label=RANK_BY_LABELS[request.rank_by],
        scope_label=_scope_label(request),
        footer_caption=f"{len(rows)} players · {linked_note}",
        rows=rows,
    )
