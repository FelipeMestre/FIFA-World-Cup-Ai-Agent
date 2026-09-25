"""Persists `IngestionJob` stage checkpoints as a pipeline progresses (the
Transfermarkt sync pipeline's own stages, or the bulk synthetic upload job's
per-table stages), so `GET /admin/ingestion/jobs/{job_id}` can report which
phase a running job is in without waiting for it to finish. Wraps the job's
own state-transition method (`record_stage_checkpoint`) and re-persists the
result through the same job repository the rest of the job lifecycle uses,
keeping its own `job` reference current across calls since `IngestionJob` is
immutable. Shared by every job type that wants stage tracking instead of
each getting its own divergent checkpoint-persisting code path.
"""

from enum import StrEnum

from src.domain.ingestion.model.ingestion_job import IngestionJob
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

    async def checkpoint(self, stage: StrEnum) -> None:
        self._job = self._job.record_stage_checkpoint(stage)
        self._job = await self._repository.update(self._job)
