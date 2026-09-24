"""Persists `IngestionJob` stage checkpoints as a Transfermarkt sync
pipeline progresses, so `GET /admin/ingestion/jobs/{job_id}` can report
which phase a running job is in without waiting for it to finish. Wraps
the job's own state-transition method (`record_stage_checkpoint`) and
re-persists the result through the same job repository the rest of the
job lifecycle uses, keeping its own `job` reference current across calls
since `IngestionJob` is immutable.
"""

from src.domain.ingestion.model.ingestion_job import IngestionJob
from src.domain.ingestion.model.transfermarkt_sync_stage import TransfermarktSyncStage
from src.infra.postgres.interfaces.ingestion_job_repository_interface import (
    IngestionJobRepositoryInterface,
)


class JobProgressTracker:
    def __init__(self, job: IngestionJob, repository: IngestionJobRepositoryInterface) -> None:
        self._job = job
        self._repository = repository

    @property
    def job(self) -> IngestionJob:
        return self._job

    async def checkpoint(self, stage: TransfermarktSyncStage) -> None:
        self._job = self._job.record_stage_checkpoint(stage)
        self._job = await self._repository.update(self._job)
