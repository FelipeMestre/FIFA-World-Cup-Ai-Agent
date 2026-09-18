"""Aggregates Transfermarkt `appearances.csv` rows into `real_player_season_stat`
rows. `appearances.csv` carries no `season`/`competition_id` column directly --
each appearance is joined to its game (by `game_id`) against an already-ingested
`games_by_id` lookup to recover those two fields before grouping.

Pure function, no I/O: fully unit-testable with in-memory fixtures.
"""

from collections.abc import Iterable
from typing import Any

from src.domain.ingestion.exceptions.ingestion_exceptions import IngestionValidationError

_SUM_COLUMNS = ("goals", "assists", "yellow_cards", "red_cards", "minutes_played")


class SeasonStatAggregationService:
    def aggregate(
        self,
        appearances_rows: Iterable[dict[str, Any]],
        games_by_id: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        groups: dict[tuple[int, str, str], dict[str, Any]] = {}
        for row in appearances_rows:
            game_id = row["game_id"]
            game = games_by_id.get(game_id)
            if game is None:
                raise IngestionValidationError(
                    f"appearance row references unknown game_id '{game_id}'"
                )
            key = (row["player_id"], game["season"], game["competition_id"])
            group = groups.get(key)
            if group is None:
                group = {
                    "real_player_id": row["player_id"],
                    "season": game["season"],
                    "competition_id": game["competition_id"],
                    "appearances": 0,
                    "goals": 0,
                    "assists": 0,
                    "yellow_cards": 0,
                    "red_cards": 0,
                    "minutes_played": 0,
                }
                groups[key] = group
            group["appearances"] += 1
            for column in _SUM_COLUMNS:
                group[column] += row[column]
        return list(groups.values())
