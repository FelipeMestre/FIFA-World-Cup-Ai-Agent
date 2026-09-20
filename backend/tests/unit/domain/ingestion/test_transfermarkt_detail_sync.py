import pytest

from src.domain.ingestion.services import transfermarkt_detail_sync as detail_sync_module
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

    counts = await sync.sync_player_scoped_tables(
        matched_real_player_ids={1}, known_club_ids={"10", "11"}
    )

    assert counts == {"player_valuations": 1, "transfers": 1}
    valuation_call = next(
        call for call in repository.calls if call[0].__tablename__ == "real_player_valuation"
    )
    assert len(valuation_call[1]) == 1
    assert valuation_call[1][0]["real_player_id"] == 1


@pytest.mark.asyncio
async def test_sync_player_scoped_tables_nulls_unresolvable_transfer_club_ids():
    # Found live against the real Transfermarkt source: a transfer can
    # reference a club_id that isn't in this clubs.csv export. Both columns
    # are nullable, so the fix nulls them rather than dropping the transfer.
    client = _FakeTransfermarktClient(
        {
            "player_valuations": [],
            "transfers": [
                {
                    "player_id": "1",
                    "transfer_date": "2025-07-01",
                    "transfer_season": "25/26",
                    "from_club_id": "999999",
                    "to_club_id": "11",
                    "from_club_name": "Unknown FC",
                    "to_club_name": "B",
                    "transfer_fee": "5000000",
                    "market_value_in_eur": "5000000",
                },
            ],
        }
    )
    repository = _FakeIngestionRepository()
    sync = _detail_sync(client, repository)

    counts = await sync.sync_player_scoped_tables(
        matched_real_player_ids={1}, known_club_ids={"11"}
    )

    assert counts["transfers"] == 1
    transfer_call = next(
        call for call in repository.calls if call[0].__tablename__ == "real_transfer"
    )
    row = transfer_call[1][0]
    assert row["from_club_id"] is None
    assert row["to_club_id"] == 11


@pytest.mark.asyncio
async def test_sync_match_data_drops_lineup_rows_with_unresolvable_club_id():
    # real_game_lineup.real_club_id is NOT NULL -- an unresolvable club_id
    # can't be nulled like the nullable transfer/event/club_game columns,
    # so the row is filtered out instead.
    client = _FakeTransfermarktClient(
        {
            "game_lineups": [
                {
                    "game_lineups_id": "1",
                    "game_id": "100",
                    "player_id": "1",
                    "club_id": "999999",
                    "type": "starting_lineup",
                    "position": "FW",
                    "number": "9",
                    "team_captain": "0",
                    "date": "2025-06-01",
                },
                {
                    "game_lineups_id": "2",
                    "game_id": "100",
                    "player_id": "1",
                    "club_id": "10",
                    "type": "starting_lineup",
                    "position": "FW",
                    "number": "9",
                    "team_captain": "0",
                    "date": "2025-06-01",
                },
            ],
            "game_events": [],
            "club_games": [],
        }
    )
    repository = _FakeIngestionRepository()
    sync = _detail_sync(client, repository)

    counts = await sync.sync_match_data(
        matched_real_player_ids={1}, matched_real_club_ids={10}, known_club_ids={"10"}
    )

    assert counts["game_lineups"] == 1
    lineup_call = next(
        call for call in repository.calls if call[0].__tablename__ == "real_game_lineup"
    )
    assert len(lineup_call[1]) == 1
    assert lineup_call[1][0]["real_club_id"] == 10


@pytest.mark.asyncio
async def test_sync_match_data_nulls_unresolvable_event_player_references():
    # Found live: game_events.player_in_id/player_assist_id reference
    # players outside the matched roster (a substitution's incoming/
    # assisting player is very often someone we never matched/persisted).
    # Both are nullable FKs into real_player, so they're nulled rather than
    # dropping the event.
    client = _FakeTransfermarktClient(
        {
            "game_lineups": [],
            "club_games": [],
            "game_events": [
                {
                    "game_event_id": "e1",
                    "date": "2025-06-01",
                    "game_id": "100",
                    "minute": "70",
                    "type": "Substitutions",
                    "club_id": "10",
                    "club_name": "Test FC",
                    "player_id": "1",
                    "description": "",
                    "player_in_id": "999999",
                    "player_assist_id": "",
                },
            ],
        }
    )
    repository = _FakeIngestionRepository()
    sync = _detail_sync(client, repository)

    counts = await sync.sync_match_data(
        matched_real_player_ids={1}, matched_real_club_ids={10}, known_club_ids={"10"}
    )

    assert counts["game_events"] == 1
    event_call = next(
        call for call in repository.calls if call[0].__tablename__ == "real_match_event"
    )
    row = event_call[1][0]
    assert row["real_player_id"] == 1
    assert row["player_in_id"] is None
    assert row["assist_player_id"] is None


@pytest.mark.asyncio
async def test_sync_match_data_nulls_unresolvable_club_game_opponent():
    client = _FakeTransfermarktClient(
        {
            "game_lineups": [],
            "game_events": [],
            "club_games": [
                {
                    "game_id": "100",
                    "club_id": "10",
                    "own_goals": "2",
                    "own_position": "1",
                    "own_manager_name": "Coach",
                    "opponent_id": "999999",
                    "opponent_goals": "1",
                    "opponent_position": "2",
                    "opponent_manager_name": "Other Coach",
                    "hosting": "home",
                    "is_win": "1",
                },
            ],
        }
    )
    repository = _FakeIngestionRepository()
    sync = _detail_sync(client, repository)

    counts = await sync.sync_match_data(
        matched_real_player_ids=set(), matched_real_club_ids={10}, known_club_ids={"10"}
    )

    assert counts["club_games"] == 1
    club_game_call = next(
        call for call in repository.calls if call[0].__tablename__ == "real_club_game"
    )
    assert club_game_call[1][0]["opponent_club_id"] is None


@pytest.mark.asyncio
async def test_sync_season_stats_joins_appearances_to_games_by_id():
    client = _FakeTransfermarktClient(
        {
            "games": [{"game_id": "100", "season": "2025", "competition_id": "FIWC"}],
            "appearances": [
                {
                    "player_id": "1",
                    "game_id": "100",
                    "goals": "1",
                    "assists": "0",
                    "yellow_cards": "0",
                    "red_cards": "0",
                    "minutes_played": "90",
                },
                {
                    "player_id": "99",
                    "game_id": "100",
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


@pytest.mark.asyncio
async def test_sync_season_stats_chunks_large_aggregated_result():
    # asyncpg caps total query parameters at 32767; unlike every other
    # table here, this upsert doesn't go through CsvIngestionService's own
    # chunking. Found live: ~14,400 aggregated rows in one INSERT exceeded
    # the limit. Use a small chunk size to keep this test fast while still
    # exercising multiple chunks.
    game_rows = [{"game_id": "g1", "season": "2025", "competition_id": "FIWC"}]
    appearance_rows = [
        {
            "player_id": str(player_id),
            "game_id": "g1",
            "goals": "0",
            "assists": "0",
            "yellow_cards": "0",
            "red_cards": "0",
            "minutes_played": "90",
        }
        for player_id in range(1, 6)
    ]
    client = _FakeTransfermarktClient({"games": game_rows, "appearances": appearance_rows})
    repository = _FakeIngestionRepository()
    sync = _detail_sync(client, repository)

    original_chunk_size = detail_sync_module._SEASON_STAT_CHUNK_SIZE
    detail_sync_module._SEASON_STAT_CHUNK_SIZE = 2
    try:
        row_count = await sync.sync_season_stats(matched_real_player_ids=set(range(1, 6)))
    finally:
        detail_sync_module._SEASON_STAT_CHUNK_SIZE = original_chunk_size

    assert row_count == 5
    season_stat_calls = [
        call for call in repository.calls if call[0].__tablename__ == "real_player_season_stat"
    ]
    assert [len(call[1]) for call in season_stat_calls] == [2, 2, 1]
