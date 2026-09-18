"""Pure unit tests for `SyntheticIngestionService` using fake repositories --
no DB, per this batch's constraint that domain-service logic must be
unit-testable in isolation.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import pytest

from src.domain.ingestion.exceptions.ingestion_exceptions import UnknownTableError
from src.domain.ingestion.model.ingestion_job import (
    IngestionJob,
    IngestionJobStatus,
    IngestionJobType,
)
from src.domain.ingestion.services.csv_ingestion_service import CsvIngestionService
from src.domain.ingestion.services.synthetic_ingestion_service import SyntheticIngestionService
from src.domain.ingestion.services.table_ingestion_spec import TableIngestionSpec
from src.infra.postgres.interfaces.ingestion_repository_interface import UpsertResult
from src.infra.postgres.schemas.team_schema import TeamSchema


@dataclass
class _FakeIngestionRepository:
    calls: list[list[dict[str, Any]]] = field(default_factory=list)

    async def upsert_many(
        self, schema_cls: type, rows: list[dict[str, Any]], conflict_columns: Sequence[str]
    ) -> UpsertResult:
        self.calls.append(rows)
        return UpsertResult(table_name=schema_cls.__tablename__, row_count=len(rows))


@dataclass
class _FakeIngestionJobRepository:
    updates: list[IngestionJob] = field(default_factory=list)

    async def create(self, job: IngestionJob) -> IngestionJob:
        return job

    async def get(self, job_id: int) -> IngestionJob | None:
        return None

    async def update(self, job: IngestionJob) -> IngestionJob:
        self.updates.append(job)
        return job


def _team_spec() -> TableIngestionSpec:
    return TableIngestionSpec(
        source_name="team",
        target_schema=TeamSchema,
        column_spec={"team_id": int, "team_name": str},
        conflict_columns=("team_id",),
    )


def _queued_job() -> IngestionJob:
    return IngestionJob(
        id=1,
        job_type=IngestionJobType.SYNTHETIC_UPLOAD,
        status=IngestionJobStatus.QUEUED,
        source_label="team.csv",
        requested_by_user_id=1,
    )


async def test_ingest_upload_marks_job_succeeded_with_row_count() -> None:
    job_repository = _FakeIngestionJobRepository()
    service = SyntheticIngestionService(
        csv_ingestion_service=CsvIngestionService(),
        ingestion_repository=_FakeIngestionRepository(),
        ingestion_job_repository=job_repository,
        table_specs=[_team_spec()],
    )
    rows = [{"team_id": "1", "team_name": "Team A"}]

    result = await service.ingest_upload("team", rows, _queued_job())

    assert result.status == IngestionJobStatus.SUCCEEDED
    assert result.row_counts == {"team": 1}
    assert [job.status for job in job_repository.updates] == [
        IngestionJobStatus.RUNNING,
        IngestionJobStatus.SUCCEEDED,
    ]


async def test_ingest_upload_marks_job_failed_on_validation_error() -> None:
    job_repository = _FakeIngestionJobRepository()
    service = SyntheticIngestionService(
        csv_ingestion_service=CsvIngestionService(),
        ingestion_repository=_FakeIngestionRepository(),
        ingestion_job_repository=job_repository,
        table_specs=[_team_spec()],
    )
    rows = [{"team_id": "not-a-number", "team_name": "Team A"}]

    result = await service.ingest_upload("team", rows, _queued_job())

    assert result.status == IngestionJobStatus.FAILED
    assert result.error_message is not None
    assert [job.status for job in job_repository.updates] == [
        IngestionJobStatus.RUNNING,
        IngestionJobStatus.FAILED,
    ]


async def test_ingest_upload_raises_on_unknown_table() -> None:
    service = SyntheticIngestionService(
        csv_ingestion_service=CsvIngestionService(),
        ingestion_repository=_FakeIngestionRepository(),
        ingestion_job_repository=_FakeIngestionJobRepository(),
        table_specs=[_team_spec()],
    )

    with pytest.raises(UnknownTableError):
        await service.ingest_upload("not_a_real_table", [], _queued_job())
