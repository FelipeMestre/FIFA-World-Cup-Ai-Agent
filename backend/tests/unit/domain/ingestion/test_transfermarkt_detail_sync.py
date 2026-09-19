import pytest

from src.domain.ingestion.services.csv_ingestion_service import CsvIngestionService
from src.domain.ingestion.services.season_stat_aggregation_service import (
    SeasonStatAggregationService,
)
from src.domain.ingestion.services.transfermarkt_detail_sync import TransfermarktDetailSync
from src.infra.postgres.interfaces.ingestion_repository_interface import UpsertResult
from src.infra.postgres.schemas.real_player_schema import RealPlayerSeasonStatSchema


class _FakeTransfermarktClient:
    def __init__(self, tables: dict[str, list[dict[str, str]]]) -> None:
        self._tables = tables

    async def stream_csv_rows(self, table_name: str):
        for row in self._tables.get(table_name, []):
            yield row


class _FakeIngestionRepository:
    def __init__(self) -> None:
        self.calls: list[tuple[type, list[dict], tuple[str, ...]]] = []

    async def upsert_many(self, schema_cls, rows, conflict_columns) -> UpsertResult:
        self.calls.append((schema_cls, rows, tuple(conflict_columns)))
        return UpsertResult(table_name=schema_cls.__tablename__, row_count=len(rows))


def _detail_sync(client: _FakeTransfermarktClient, repository: _FakeIngestionRepository):
    return TransfermarktDetailSync(
        transfermarkt_client=client,
        csv_ingestion_service=CsvIngestionService(),
        ingestion_repository=repository,
        season_stat_aggregation_service=SeasonStatAggregationService(),
    )


@pytest.mark.asyncio
async def test_sync_player_scoped_tables_filters_by_matched_player_ids():
    client = _FakeTransfermarktClient(
        {
            "player_valuations": [
                {"player_id": "1", "date": "2026-01-01", "market_value_in_eur": "1000"},
                {"player_id": "2", "date": "2026-01-01", "market_value_in_eur": "2000"},
            ],
            "transfers": [
                {
                    "player_id": "1",
                    "transfer_date": "2025-07-01",
                    "transfer_season": "25/26",
                    "from_club_id": "10",
                    "to_club_id": "11",
                    "from_club_name": "A",
                    "to_club_name": "B",
                    "transfer_fee": "5000000",
                    "market_value_in_eur": "5000000",
                },
            ],
        }
    )
    repository = _FakeIngestionRepository()
    sync = _detail_sync(client, repository)

    counts = await sync.sync_player_scoped_tables(matched_real_player_ids={1})

    assert counts == {"player_valuations": 1, "transfers": 1}
    valuation_call = next(
        call for call in repository.calls if call[0].__tablename__ == "real_player_valuation"
    )
    assert len(valuation_call[1]) == 1
    assert valuation_call[1][0]["real_player_id"] == 1


@pytest.mark.asyncio
async def test_sync_season_stats_joins_appearances_to_games_by_id():
    client = _FakeTransfermarktClient(
        {
            "games": [{"game_id": "g1", "season": "2025", "competition_id": "FIWC"}],
            "appearances": [
                {
                    "player_id": "1",
                    "game_id": "g1",
                    "goals": "1",
                    "assists": "0",
                    "yellow_cards": "0",
                    "red_cards": "0",
                    "minutes_played": "90",
                },
                {
                    "player_id": "99",
                    "game_id": "g1",
                    "goals": "2",
                    "assists": "1",
                    "yellow_cards": "0",
                    "red_cards": "0",
                    "minutes_played": "90",
                },
            ],
        }
    )
    repository = _FakeIngestionRepository()
    sync = _detail_sync(client, repository)

    row_count = await sync.sync_season_stats(matched_real_player_ids={1})

    assert row_count == 1
    schema_cls, rows, conflict_columns = repository.calls[0]
    assert schema_cls is RealPlayerSeasonStatSchema
    assert conflict_columns == ("real_player_id", "season", "competition_id")
    assert rows == [
        {
            "real_player_id": 1,
            "season": "2025",
            "competition_id": "FIWC",
            "appearances": 1,
            "goals": 1,
            "assists": 0,
            "yellow_cards": 0,
            "red_cards": 0,
            "minutes_played": 90,
        }
    ]


@pytest.mark.asyncio
async def test_sync_season_stats_returns_zero_when_no_matched_appearances():
    client = _FakeTransfermarktClient({"games": [], "appearances": []})
    repository = _FakeIngestionRepository()
    sync = _detail_sync(client, repository)

    row_count = await sync.sync_season_stats(matched_real_player_ids={1})

    assert row_count == 0
    assert repository.calls == []
