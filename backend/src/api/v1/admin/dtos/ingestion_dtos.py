from pydantic import BaseModel

from src.domain.ingestion.model.ingestion_job import IngestionJob, IngestionJobType
from src.domain.ingestion.model.transfermarkt_sync_stage import TransfermarktSyncStage


class SyntheticUploadResponse(BaseModel):
    job_id: int
    status: str


class BulkFileResult(BaseModel):
    filename: str
    table_name: str | None
    accepted: bool
    reason: str | None = None


class BulkSyntheticUploadResponse(BaseModel):
    job_id: int
    status: str
    files: list[BulkFileResult]


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


class StageCheckpoint(BaseModel):
    stage: str
    completed_at: str


class JobStatusResponse(BaseModel):
    job_id: int
    job_type: str
    status: str
    row_counts: dict[str, int]
    error_message: str | None
    current_stage: str | None
    stage_checkpoints: list[StageCheckpoint]
    """Every stage a `transfermarkt_sync` job's pipeline goes through, in
    order -- lets a client render "stage N of len(all_stages)" without
    duplicating this list. Always empty for a `synthetic_upload` job, which
    has no sub-stages.
    """
    all_stages: list[str]

    @classmethod
    def from_domain(cls, job: IngestionJob) -> "JobStatusResponse":
        return cls(
            job_id=job.id,
            job_type=job.job_type.value,
            status=job.status.value,
            row_counts=job.row_counts,
            error_message=job.error_message,
            current_stage=job.current_stage,
            stage_checkpoints=[
                StageCheckpoint(**checkpoint) for checkpoint in job.stage_checkpoints
            ],
            all_stages=(
                [stage.value for stage in TransfermarktSyncStage]
                if job.job_type == IngestionJobType.TRANSFERMARKT_SYNC
                else []
            ),
        )
