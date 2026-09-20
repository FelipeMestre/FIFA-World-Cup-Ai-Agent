from pydantic import BaseModel

from src.domain.ingestion.model.ingestion_job import IngestionJob


class SyntheticUploadResponse(BaseModel):
    job_id: int
    status: str


class TransfermarktSyncRequest(BaseModel):
    skip_populated: bool = False
    """Resume mode: a step whose target table already has rows is skipped
    instead of re-fetching and re-upserting its source CSV (some of which
    are millions of rows). Off by default -- a sync always runs in full
    unless explicitly asked to resume.
    """


class SyncTriggerResponse(BaseModel):
    job_id: int
    status: str


class JobStatusResponse(BaseModel):
    job_id: int
    job_type: str
    status: str
    row_counts: dict[str, int]
    error_message: str | None

    @classmethod
    def from_domain(cls, job: IngestionJob) -> "JobStatusResponse":
        return cls(
            job_id=job.id,
            job_type=job.job_type.value,
            status=job.status.value,
            row_counts=job.row_counts,
            error_message=job.error_message,
        )
