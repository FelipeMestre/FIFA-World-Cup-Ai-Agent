"""Pure unit tests for `BulkSyntheticIngestionService` and its
`resolve_and_order_files` helper, using fake repositories and real CSV bytes
-- no DB, no mocking of business logic, per AGENTS.md's testing
anti-pattern table.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from src.domain.ingestion.model.ingestion_job import (
    IngestionJob,
    IngestionJobStatus,
    IngestionJobType,
)
from src.domain.ingestion.services.bulk_synthetic_ingestion_service import (
    BulkSyntheticIngestionService,
    resolve_and_order_files,
)
from src.domain.ingestion.services.csv_ingestion_service import CsvIngestionService
from src.domain.ingestion.services.table_ingestion_spec import TableIngestionSpec
from src.infra.postgres.interfaces.ingestion_repository_interface import UpsertResult
from src.infra.postgres.schemas.national_team_schema import NationalTeamSchema
from src.infra.postgres.schemas.player_schema import PlayerSchema


@dataclass
class _FakeIngestionRepository:
    calls: list[tuple[str, list[dict[str, Any]]]] = field(default_factory=list)

    async def upsert_many(
        self, schema_cls: type, rows: list[dict[str, Any]], conflict_columns: Sequence[str]
    ) -> UpsertResult:
        self.calls.append((schema_cls.__tablename__, rows))
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
        target_schema=NationalTeamSchema,
        column_spec={"team_id": int, "team_name": str},
        conflict_columns=("team_id",),
    )


def _player_spec() -> TableIngestionSpec:
    return TableIngestionSpec(
        source_name="player",
        target_schema=PlayerSchema,
        column_spec={"player_id": int, "player_name": str},
        conflict_columns=("player_id",),
    )


def _queued_job() -> IngestionJob:
    return IngestionJob(
        id=1,
        job_type=IngestionJobType.BULK_SYNTHETIC_UPLOAD,
        status=IngestionJobStatus.QUEUED,
        source_label="teams.csv,squads_and_players.csv",
        requested_by_user_id=1,
    )


def test_resolve_and_order_files_sorts_regardless_of_upload_order() -> None:
    # Uploaded in child-before-parent order -- must come back parent-first.
    scrambled = [
        ("squads_and_players.csv", b"player_id,player_name\n1,Player A\n"),
        ("teams.csv", b"team_id,team_name\n1,Team A\n"),
    ]

    resolution = resolve_and_order_files(scrambled)

    assert [f.table_name for f in resolution.accepted] == ["team", "player"]
    assert resolution.rejected == []


def test_resolve_and_order_files_rejects_unrecognized_filename_without_dropping_others() -> None:
    files = [
        ("teams.csv", b"team_id,team_name\n1,Team A\n"),
        ("mystery_export.csv", b"a,b\n1,2\n"),
    ]

    resolution = resolve_and_order_files(files)

    assert [f.table_name for f in resolution.accepted] == ["team"]
    assert len(resolution.rejected) == 1
    assert resolution.rejected[0].filename == "mystery_export.csv"
    assert "mystery_export.csv" in resolution.rejected[0].reason


async def test_ingest_batch_marks_job_succeeded_with_accumulated_row_counts() -> None:
    job_repository = _FakeIngestionJobRepository()
    service = BulkSyntheticIngestionService(
        csv_ingestion_service=CsvIngestionService(),
        ingestion_repository=_FakeIngestionRepository(),
        ingestion_job_repository=job_repository,
        table_specs=[_team_spec(), _player_spec()],
    )
    resolution = resolve_and_order_files(
        [
            ("squads_and_players.csv", b"player_id,player_name\n1,Player A\n2,Player B\n"),
            ("teams.csv", b"team_id,team_name\n1,Team A\n"),
        ]
    )

    result = await service.ingest_batch(resolution.accepted, _queued_job())

    assert result.status == IngestionJobStatus.SUCCEEDED
    assert result.row_counts == {"team": 1, "player": 2}
    assert [job.status for job in job_repository.updates] == [
        IngestionJobStatus.RUNNING,
        IngestionJobStatus.SUCCEEDED,
    ]


async def test_ingest_batch_marks_job_failed_on_validation_error() -> None:
    job_repository = _FakeIngestionJobRepository()
    service = BulkSyntheticIngestionService(
        csv_ingestion_service=CsvIngestionService(),
        ingestion_repository=_FakeIngestionRepository(),
        ingestion_job_repository=job_repository,
        table_specs=[_team_spec()],
    )
    resolution = resolve_and_order_files(
        [("teams.csv", b"team_id,team_name\nnot-a-number,Team A\n")]
    )

    result = await service.ingest_batch(resolution.accepted, _queued_job())

    assert result.status == IngestionJobStatus.FAILED
    assert result.error_message is not None
    assert [job.status for job in job_repository.updates] == [
        IngestionJobStatus.RUNNING,
        IngestionJobStatus.FAILED,
    ]
