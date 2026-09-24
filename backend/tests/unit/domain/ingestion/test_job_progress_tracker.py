import pytest

from src.domain.ingestion.model.ingestion_job import (
    IngestionJob,
    IngestionJobStatus,
    IngestionJobType,
)
from src.domain.ingestion.model.transfermarkt_sync_stage import TransfermarktSyncStage
from src.domain.ingestion.services.job_progress_tracker import JobProgressTracker


def _running_job() -> IngestionJob:
    return IngestionJob(
        id=1,
        job_type=IngestionJobType.TRANSFERMARKT_SYNC,
        status=IngestionJobStatus.RUNNING,
        source_label="full-sync",
        requested_by_user_id=1,
    )


class _FakeJobRepository:
    def __init__(self) -> None:
        self.updates: list[IngestionJob] = []

    async def create(self, job: IngestionJob) -> IngestionJob:  # pragma: no cover - unused
        raise NotImplementedError

    async def get(self, job_id: int) -> IngestionJob | None:  # pragma: no cover - unused
        raise NotImplementedError

    async def update(self, job: IngestionJob) -> IngestionJob:
        self.updates.append(job)
        return job


@pytest.mark.asyncio
async def test_checkpoint_persists_the_stage_via_the_repository() -> None:
    repository = _FakeJobRepository()
    tracker = JobProgressTracker(_running_job(), repository)

    await tracker.checkpoint(TransfermarktSyncStage.CLUBS)

    assert len(repository.updates) == 1
    assert repository.updates[0].current_stage == "clubs"
    assert tracker.job.current_stage == "clubs"


@pytest.mark.asyncio
async def test_checkpoint_keeps_its_job_reference_current_across_calls() -> None:
    # IngestionJob is immutable -- each checkpoint() must persist onto the
    # result of the PREVIOUS checkpoint, not re-derive from the original job
    # the tracker was constructed with (which would silently drop earlier
    # checkpoints).
    repository = _FakeJobRepository()
    tracker = JobProgressTracker(_running_job(), repository)

    await tracker.checkpoint(TransfermarktSyncStage.NATIONAL_TEAMS)
    await tracker.checkpoint(TransfermarktSyncStage.CLUBS)

    assert [c["stage"] for c in tracker.job.stage_checkpoints] == ["national_teams", "clubs"]
    assert [c["stage"] for c in repository.updates[-1].stage_checkpoints] == [
        "national_teams",
        "clubs",
    ]
