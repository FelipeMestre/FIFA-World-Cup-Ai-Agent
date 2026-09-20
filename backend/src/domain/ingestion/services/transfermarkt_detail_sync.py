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
    row: dict[str, str], column: str, matched_real_player_ids: set[int]
) -> dict[str, str]:
    """Same idea as `_sanitize_club_reference`, but against the set of
    `real_player` rows actually persisted this run (only matched roster
    players, not every player Transfermarkt ever mentions). Found live:
    `game_events.player_in_id`/`assist_player_id` -- a substitution event's
    incoming/assisting player is very often someone outside the matched
    roster.
    """
    if row.get(column) and int(row[column]) not in matched_real_player_ids:
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
        self, matched_real_player_ids: set[int], known_club_ids: set[str]
    ) -> dict[str, int]:
        """Valuations and transfers: scoped by `player_id` membership."""
        counts: dict[str, int] = {}
        for source_name in ("player_valuations", "transfers"):
            spec = _DETAIL_SPECS_BY_NAME[source_name]
            rows = await _buffer(self._client.stream_csv_rows(source_name))
            scoped = [row for row in rows if int(row["player_id"]) in matched_real_player_ids]
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
        matched_real_player_ids: set[int],
        matched_real_club_ids: set[int],
        known_club_ids: set[str],
    ) -> dict[str, int]:
        """Lineups, events, and club-games: scoped by matched player or club
        involvement (a row with no player reference, e.g. a club-level
        club_games row, is scoped by club instead).
        """
        counts: dict[str, int] = {}

        lineup_rows = await _buffer(self._client.stream_csv_rows("game_lineups"))
        # real_game_lineup.real_club_id is NOT NULL -- an unresolvable
        # club_id can't be nulled, so the row is filtered out instead.
        scoped_lineups = [
            row
            for row in lineup_rows
            if int(row["player_id"]) in matched_real_player_ids and row["club_id"] in known_club_ids
        ]
        counts["game_lineups"] = await self._csv_ingestion_service.ingest_rows(
            _DETAIL_SPECS_BY_NAME["game_lineups"], scoped_lineups, self._ingestion_repository
        )

        event_rows = await _buffer(self._client.stream_csv_rows("game_events"))
        # real_player_id (from player_id), player_in_id, and
        # assist_player_id (from player_assist_id) are all nullable FKs into
        # real_player, but only matched roster players were persisted this
        # run -- a substitution's incoming/assisting player is very often
        # someone outside that set.
        scoped_events = []
        for row in event_rows:
            if not (
                (row.get("player_id") and int(row["player_id"]) in matched_real_player_ids)
                or (row.get("club_id") and int(row["club_id"]) in matched_real_club_ids)
            ):
                continue
            row = _sanitize_club_reference(row, "club_id", known_club_ids)
            for column in ("player_id", "player_in_id", "player_assist_id"):
                row = _sanitize_player_reference(row, column, matched_real_player_ids)
            scoped_events.append(row)
        counts["game_events"] = await self._csv_ingestion_service.ingest_rows(
            _DETAIL_SPECS_BY_NAME["game_events"], scoped_events, self._ingestion_repository
        )

        club_game_rows = await _buffer(self._client.stream_csv_rows("club_games"))
        # club_id is part of the composite primary key (NOT NULL) but is
        # already guaranteed valid here: matched_real_club_ids is derived
        # only from sanitized (known-valid) player rows upstream.
        # opponent_id is nullable and NOT scoped, so it still needs sanitizing.
        scoped_club_games = [
            _sanitize_club_reference(row, "opponent_id", known_club_ids)
            for row in club_game_rows
            if int(row["club_id"]) in matched_real_club_ids
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
