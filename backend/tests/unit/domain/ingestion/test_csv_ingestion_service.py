"""Pure unit tests for `CsvIngestionService` using a fake
`IngestionRepositoryInterface` -- no DB, per this batch's constraint that
domain-service logic must be unit-testable in isolation.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import pytest

from src.domain.ingestion.exceptions.ingestion_exceptions import IngestionValidationError
from src.domain.ingestion.services.csv_ingestion_service import CsvIngestionService
from src.domain.ingestion.services.table_ingestion_spec import TableIngestionSpec
from src.infra.postgres.interfaces.ingestion_repository_interface import UpsertResult
from src.infra.postgres.schemas.national_team_schema import NationalTeamSchema


@dataclass
class _FakeIngestionRepository:
    """Records every `upsert_many` call instead of touching a real DB."""

    calls: list[list[dict[str, Any]]] = field(default_factory=list)

    async def upsert_many(
        self, schema_cls: type, rows: list[dict[str, Any]], conflict_columns: Sequence[str]
    ) -> UpsertResult:
        self.calls.append(rows)
        return UpsertResult(table_name=schema_cls.__tablename__, row_count=len(rows))


def _team_spec() -> TableIngestionSpec:
    return TableIngestionSpec(
        source_name="team",
        target_schema=NationalTeamSchema,
        column_spec={"team_id": int, "team_name": str},
        conflict_columns=("team_id",),
    )


async def test_ingest_rows_batches_by_chunk_size() -> None:
    repository = _FakeIngestionRepository()
    service = CsvIngestionService()
    rows = [{"team_id": str(i), "team_name": f"Team {i}"} for i in range(5)]

    total = await service.ingest_rows(_team_spec(), rows, repository, chunk_size=2)

    assert total == 5
    assert [len(batch) for batch in repository.calls] == [2, 2, 1]
    assert repository.calls[0][0] == {"team_id": 0, "team_name": "Team 0"}


async def test_ingest_rows_with_no_rows_is_a_noop() -> None:
    repository = _FakeIngestionRepository()
    service = CsvIngestionService()

    total = await service.ingest_rows(_team_spec(), [], repository)

    assert total == 0
    assert repository.calls == []


async def test_ingest_rows_raises_on_bad_column_value_naming_row_and_column() -> None:
    repository = _FakeIngestionRepository()
    service = CsvIngestionService()
    rows = [
        {"team_id": "1", "team_name": "Valid"},
        {"team_id": "not-a-number", "team_name": "Invalid"},
    ]

    with pytest.raises(IngestionValidationError) as exc_info:
        await service.ingest_rows(_team_spec(), rows, repository)

    assert "1" in str(exc_info.value)
    assert "team_id" in str(exc_info.value)
    assert repository.calls == [], "no partial batch should be committed once a row fails"


async def test_ingest_rows_raises_on_missing_column() -> None:
    repository = _FakeIngestionRepository()
    service = CsvIngestionService()
    rows = [{"team_id": "1"}]

    with pytest.raises(IngestionValidationError) as exc_info:
        await service.ingest_rows(_team_spec(), rows, repository)

    assert "team_name" in str(exc_info.value)


async def test_ingest_rows_dedupes_same_batch_conflict_key_keeping_the_last_row() -> None:
    # Postgres's ON CONFLICT DO UPDATE raises CardinalityViolationError if
    # one INSERT statement would affect the same conflict-key row twice.
    # Found live: a real Transfermarkt transfers.csv chunk had two rows for
    # the same (real_player_id, transfer_date) key.
    repository = _FakeIngestionRepository()
    service = CsvIngestionService()
    rows = [
        {"team_id": "1", "team_name": "First"},
        {"team_id": "1", "team_name": "Second"},
        {"team_id": "2", "team_name": "Unique"},
    ]

    total = await service.ingest_rows(_team_spec(), rows, repository, chunk_size=10)

    assert total == 2
    persisted = {row["team_id"]: row["team_name"] for row in repository.calls[0]}
    assert persisted == {1: "Second", 2: "Unique"}


async def test_ingest_rows_applies_row_transform() -> None:
    repository = _FakeIngestionRepository()
    service = CsvIngestionService()
    spec = TableIngestionSpec(
        source_name="team",
        target_schema=NationalTeamSchema,
        column_spec={"team_id": int, "team_name": str},
        conflict_columns=("team_id",),
        row_transform=lambda row: {**row, "team_name": row["team_name"].upper()},
    )

    await service.ingest_rows(spec, [{"team_id": "1", "team_name": "lower"}], repository)

    assert repository.calls[0][0]["team_name"] == "LOWER"
