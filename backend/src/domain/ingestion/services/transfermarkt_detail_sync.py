"""Scoped detail-pull half of the Transfermarkt sync pipeline: valuations,
transfers, match data, and season-stat aggregation. Every pull is filtered
to the matched player/club scope `TransfermarktSyncService` resolves first,
so the working set stays in the hundreds, never the source dataset's size.
"""

from collections.abc import AsyncIterator
from typing import Any

from src.domain.ingestion.services.csv_ingestion_service import CsvIngestionService
from src.domain.ingestion.services.season_stat_aggregation_service import (
    SeasonStatAggregationService,
)
from src.domain.ingestion.services.transfermarkt_detail_specs import TRANSFERMARKT_DETAIL_SPECS
from src.infra.postgres.interfaces.ingestion_repository_interface import (
    IngestionRepositoryInterface,
)
from src.infra.postgres.schemas.real_player_schema import RealPlayerSeasonStatSchema
from src.infra.transfermarkt.client_interface import TransfermarktClientInterface

_DETAIL_SPECS_BY_NAME = {spec.source_name: spec for spec in TRANSFERMARKT_DETAIL_SPECS}
_SEASON_STAT_CONFLICT_COLUMNS = ("real_player_id", "season", "competition_id")


async def _buffer(rows: AsyncIterator[dict[str, str]]) -> list[dict[str, str]]:
    return [row async for row in rows]


class TransfermarktDetailSync:
    def __init__(
        self,
        transfermarkt_client: TransfermarktClientInterface,
        csv_ingestion_service: CsvIngestionService,
        ingestion_repository: IngestionRepositoryInterface,
        season_stat_aggregation_service: SeasonStatAggregationService,
    ) -> None:
        self._client = transfermarkt_client
        self._csv_ingestion_service = csv_ingestion_service
        self._ingestion_repository = ingestion_repository
        self._season_stat_aggregation_service = season_stat_aggregation_service

    async def sync_player_scoped_tables(self, matched_real_player_ids: set[int]) -> dict[str, int]:
        """Valuations and transfers: scoped by `player_id` membership."""
        counts: dict[str, int] = {}
        for source_name in ("player_valuations", "transfers"):
            spec = _DETAIL_SPECS_BY_NAME[source_name]
            rows = await _buffer(self._client.stream_csv_rows(source_name))
            scoped = [row for row in rows if int(row["player_id"]) in matched_real_player_ids]
            counts[source_name] = await self._csv_ingestion_service.ingest_rows(
                spec, scoped, self._ingestion_repository
            )
        return counts

    async def sync_match_data(
        self, matched_real_player_ids: set[int], matched_real_club_ids: set[int]
    ) -> dict[str, int]:
        """Lineups, events, and club-games: scoped by matched player or club
        involvement (a row with no player reference, e.g. a club-level
        club_games row, is scoped by club instead).
        """
        counts: dict[str, int] = {}

        lineup_rows = await _buffer(self._client.stream_csv_rows("game_lineups"))
        scoped_lineups = [
            row for row in lineup_rows if int(row["player_id"]) in matched_real_player_ids
        ]
        counts["game_lineups"] = await self._csv_ingestion_service.ingest_rows(
            _DETAIL_SPECS_BY_NAME["game_lineups"], scoped_lineups, self._ingestion_repository
        )

        event_rows = await _buffer(self._client.stream_csv_rows("game_events"))
        scoped_events = [
            row
            for row in event_rows
            if (row.get("player_id") and int(row["player_id"]) in matched_real_player_ids)
            or (row.get("club_id") and int(row["club_id"]) in matched_real_club_ids)
        ]
        counts["game_events"] = await self._csv_ingestion_service.ingest_rows(
            _DETAIL_SPECS_BY_NAME["game_events"], scoped_events, self._ingestion_repository
        )

        club_game_rows = await _buffer(self._client.stream_csv_rows("club_games"))
        scoped_club_games = [
            row for row in club_game_rows if int(row["club_id"]) in matched_real_club_ids
        ]
        counts["club_games"] = await self._csv_ingestion_service.ingest_rows(
            _DETAIL_SPECS_BY_NAME["club_games"], scoped_club_games, self._ingestion_repository
        )
        return counts

    async def sync_season_stats(self, matched_real_player_ids: set[int]) -> int:
        """`appearances.csv` has no `season` column directly -- join against
        `games.csv` by `game_id` first (games.csv itself has no target
        table; it exists only to recover `season`/`competition_id`), then
        aggregate via `SeasonStatAggregationService` before upserting.
        """
        game_rows = await _buffer(self._client.stream_csv_rows("games"))
        games_by_id: dict[str, dict[str, Any]] = {
            row["game_id"]: {"season": row["season"], "competition_id": row["competition_id"]}
            for row in game_rows
        }

        appearance_rows = await _buffer(self._client.stream_csv_rows("appearances"))
        scoped_appearances = [
            {
                "player_id": int(row["player_id"]),
                "game_id": row["game_id"],
                "goals": int(row["goals"]),
                "assists": int(row["assists"]),
                "yellow_cards": int(row["yellow_cards"]),
                "red_cards": int(row["red_cards"]),
                "minutes_played": int(row["minutes_played"]),
            }
            for row in appearance_rows
            if int(row["player_id"]) in matched_real_player_ids
        ]

        aggregated = self._season_stat_aggregation_service.aggregate(
            scoped_appearances, games_by_id
        )
        if not aggregated:
            return 0
        result = await self._ingestion_repository.upsert_many(
            RealPlayerSeasonStatSchema, aggregated, _SEASON_STAT_CONFLICT_COLUMNS
        )
        return result.row_count
