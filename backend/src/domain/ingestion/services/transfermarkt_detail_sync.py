"""Scoped detail-pull half of the Transfermarkt sync pipeline: valuations,
transfers, match data, and season-stat aggregation. Every pull is filtered
to the `real_player`/`real_club` ids `TransfermarktSyncService` has already
persisted -- every Transfermarkt player, not only ones linked to a WC2026
roster player -- so a detail row referencing an id this sync never ingested
(e.g. an unscraped historical player) is dropped rather than violating a
foreign key.
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
from src.infra.postgres.schemas.real_match_data_schema import (
    RealClubGameSchema,
    RealGameLineupSchema,
    RealMatchEventSchema,
)
from src.infra.postgres.schemas.real_player_schema import (
    RealPlayerSeasonStatSchema,
    RealPlayerValuationSchema,
    RealTransferSchema,
)
from src.infra.transfermarkt.client_interface import TransfermarktClientInterface

_DETAIL_SPECS_BY_NAME = {spec.source_name: spec for spec in TRANSFERMARKT_DETAIL_SPECS}
_SCHEMA_BY_SOURCE_NAME = {
    "player_valuations": RealPlayerValuationSchema,
    "transfers": RealTransferSchema,
    "game_lineups": RealGameLineupSchema,
    "game_events": RealMatchEventSchema,
    "club_games": RealClubGameSchema,
}
_SEASON_STAT_CONFLICT_COLUMNS = ("real_player_id", "season", "competition_id")
# asyncpg caps total query parameters at 32767; real_player_season_stat has
# 9 columns, and unlike every other table here this upsert doesn't go
# through CsvIngestionService's own chunking (there's no CSV row to chunk --
# the aggregated rows are already in memory). Found live: a real run with
# ~14,400 aggregated rows (129,915 parameters) exceeded the limit in one
# INSERT.
_SEASON_STAT_CHUNK_SIZE = 500


async def _buffer(rows: AsyncIterator[dict[str, str]]) -> list[dict[str, str]]:
    return [row async for row in rows]


def _sanitize_club_reference(
    row: dict[str, str], column: str, known_club_ids: set[str]
) -> dict[str, str]:
    """Blanks `row[column]` if it doesn't resolve to an ingested `real_club`
    row (found live: a player/transfer/event row can reference a club_id
    Transfermarkt's own `clubs.csv` export never carries -- an upstream data
    gap, not a bug here). `parsers.parse_optional_int` already treats an
    empty string as `None`, so this reuses that existing null path. Only
    safe for nullable FK columns -- a NOT NULL column (e.g.
    `real_game_lineup.real_club_id`) must filter the row out instead.
    """
    if row.get(column) and row[column] not in known_club_ids:
        row = {**row, column: ""}
    return row


def _sanitize_player_reference(
    row: dict[str, str], column: str, real_player_ids: set[int]
) -> dict[str, str]:
    """Same idea as `_sanitize_club_reference`, but against the set of
    `real_player` rows actually persisted this run. Found live:
    `game_events.player_in_id`/`assist_player_id` can reference a player_id
    `players.csv` itself never carries (an upstream data gap), so even the
    now-exhaustive persisted set doesn't guarantee a hit.
    """
    if row.get(column) and int(row[column]) not in real_player_ids:
        row = {**row, column: ""}
    return row


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

    async def sync_player_scoped_tables(
        self,
        real_player_ids: set[int],
        known_club_ids: set[str],
        skip_populated: bool = False,
    ) -> dict[str, int]:
        """Valuations and transfers: scoped by `player_id` membership."""
        counts: dict[str, int] = {}
        for source_name in ("player_valuations", "transfers"):
            if skip_populated and await self._ingestion_repository.has_rows(
                _SCHEMA_BY_SOURCE_NAME[source_name]
            ):
                counts[source_name] = 0
                continue
            spec = _DETAIL_SPECS_BY_NAME[source_name]
            rows = await _buffer(self._client.stream_csv_rows(source_name))
            scoped = [row for row in rows if int(row["player_id"]) in real_player_ids]
            if source_name == "transfers":
                # from_club_id/to_club_id are nullable -- null out any that
                # don't resolve rather than dropping the transfer row.
                scoped = [
                    _sanitize_club_reference(
                        _sanitize_club_reference(row, "from_club_id", known_club_ids),
                        "to_club_id",
                        known_club_ids,
                    )
                    for row in scoped
                ]
            counts[source_name] = await self._csv_ingestion_service.ingest_rows(
                spec, scoped, self._ingestion_repository
            )
        return counts

    async def sync_match_data(
        self,
        real_player_ids: set[int],
        real_club_ids: set[int],
        known_club_ids: set[str],
        skip_populated: bool = False,
    ) -> dict[str, int]:
        """Lineups, events, and club-games: scoped by persisted player or
        club involvement (a row with no player reference, e.g. a club-level
        club_games row, is scoped by club instead).
        """
        counts: dict[str, int] = {}

        if skip_populated and await self._ingestion_repository.has_rows(RealGameLineupSchema):
            counts["game_lineups"] = 0
        else:
            lineup_rows = await _buffer(self._client.stream_csv_rows("game_lineups"))
            # real_game_lineup.real_club_id is NOT NULL -- an unresolvable
            # club_id can't be nulled, so the row is filtered out instead.
            scoped_lineups = [
                row
                for row in lineup_rows
                if int(row["player_id"]) in real_player_ids and row["club_id"] in known_club_ids
            ]
            counts["game_lineups"] = await self._csv_ingestion_service.ingest_rows(
                _DETAIL_SPECS_BY_NAME["game_lineups"], scoped_lineups, self._ingestion_repository
            )

        if skip_populated and await self._ingestion_repository.has_rows(RealMatchEventSchema):
            counts["game_events"] = 0
        else:
            event_rows = await _buffer(self._client.stream_csv_rows("game_events"))
            # real_player_id (from player_id), player_in_id, and
            # assist_player_id (from player_assist_id) are all nullable FKs
            # into real_player. Even with every Transfermarkt player now
            # persisted, an event can still reference a player_id
            # players.csv itself never carries (an upstream data gap).
            scoped_events = []
            for row in event_rows:
                if not (
                    (row.get("player_id") and int(row["player_id"]) in real_player_ids)
                    or (row.get("club_id") and int(row["club_id"]) in real_club_ids)
                ):
                    continue
                row = _sanitize_club_reference(row, "club_id", known_club_ids)
                for column in ("player_id", "player_in_id", "player_assist_id"):
                    row = _sanitize_player_reference(row, column, real_player_ids)
                scoped_events.append(row)
            counts["game_events"] = await self._csv_ingestion_service.ingest_rows(
                _DETAIL_SPECS_BY_NAME["game_events"], scoped_events, self._ingestion_repository
            )

        if skip_populated and await self._ingestion_repository.has_rows(RealClubGameSchema):
            counts["club_games"] = 0
        else:
            club_game_rows = await _buffer(self._client.stream_csv_rows("club_games"))
            # club_id is part of the composite primary key (NOT NULL) but is
            # already guaranteed valid here: real_club_ids is derived only
            # from sanitized (known-valid) player rows upstream. opponent_id
            # is nullable and NOT scoped, so it still needs sanitizing.
            scoped_club_games = [
                _sanitize_club_reference(row, "opponent_id", known_club_ids)
                for row in club_game_rows
                if int(row["club_id"]) in real_club_ids
            ]
            counts["club_games"] = await self._csv_ingestion_service.ingest_rows(
                _DETAIL_SPECS_BY_NAME["club_games"], scoped_club_games, self._ingestion_repository
            )
        return counts

    async def sync_season_stats(
        self, real_player_ids: set[int], skip_populated: bool = False
    ) -> int:
        """`appearances.csv` has no `season` column directly -- join against
        `games.csv` by `game_id` first (games.csv itself has no target
        table; it exists only to recover `season`/`competition_id`), then
        aggregate via `SeasonStatAggregationService` before upserting.
        """
        if skip_populated and await self._ingestion_repository.has_rows(RealPlayerSeasonStatSchema):
            return 0

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
            if int(row["player_id"]) in real_player_ids
        ]

        aggregated = self._season_stat_aggregation_service.aggregate(
            scoped_appearances, games_by_id
        )
        total = 0
        for start in range(0, len(aggregated), _SEASON_STAT_CHUNK_SIZE):
            chunk = aggregated[start : start + _SEASON_STAT_CHUNK_SIZE]
            result = await self._ingestion_repository.upsert_many(
                RealPlayerSeasonStatSchema, chunk, _SEASON_STAT_CONFLICT_COLUMNS
            )
            total += result.row_count
        return total
