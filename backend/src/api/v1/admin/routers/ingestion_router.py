"""Admin-only ingestion endpoints: upload a synthetic CSV table, trigger a
Transfermarkt sync, and poll job status. Every route enqueues work onto the
Arq worker rather than running it inline -- per AGENTS.md's own async-work
table, ingesting hundreds-to-thousands of rows is not `BackgroundTasks`
territory. The uploaded CSV's bytes travel through the job payload rather
than a shared filesystem path: the API and worker run in separate
containers, so a path written here would not be visible to the worker.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from src.api.v1.admin.dtos.ingestion_dtos import (
    JobStatusResponse,
    SyncTriggerResponse,
    SyntheticUploadResponse,
    TransfermarktSyncRequest,
)
from src.api.v1.admin.services.upload_table_validation_service import validate_known_table
from src.api.v1.auth.services.dependencies import require_admin
from src.domain.ingestion.model.ingestion_job import (
    IngestionJob,
    IngestionJobStatus,
    IngestionJobType,
)
from src.infra.postgres.interfaces.ingestion_job_repository_interface import (
    IngestionJobRepositoryInterface,
)
from src.infra.postgres.repositories.ingestion_job_repository import get_ingestion_job_repository
from src.infra.task_queue.pool import enqueue_synthetic_upload, enqueue_transfermarkt_sync

router = APIRouter(prefix="/admin/ingestion", tags=["admin-ingestion"])

AdminDep = Annotated[dict, Depends(require_admin)]
IngestionJobRepositoryDep = Annotated[
    IngestionJobRepositoryInterface, Depends(get_ingestion_job_repository)
]

_MAX_UPLOAD_BYTES = 50 * 1024 * 1024
_ALLOWED_CONTENT_TYPES = {"text/csv", "application/vnd.ms-excel", "application/octet-stream"}


@router.post(
    "/synthetic-upload",
    response_model=SyntheticUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a synthetic CSV table for ingestion",
    description="Admin-only. Validates the table name and file, queues the "
    "upload for asynchronous ingestion, and returns a job id to poll.",
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Unknown table, wrong file type, or oversized file"
        }
    },
)
async def upload_synthetic_csv(
    admin: AdminDep,
    job_repository: IngestionJobRepositoryDep,
    table_name: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
) -> SyntheticUploadResponse:
    validate_known_table(table_name)
    if file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unsupported content type '{file.content_type}', expected a CSV",
        )
    contents = await file.read(_MAX_UPLOAD_BYTES + 1)
    if len(contents) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"file exceeds the {_MAX_UPLOAD_BYTES // (1024 * 1024)}MB upload limit",
        )

    job = IngestionJob(
        id=None,
        job_type=IngestionJobType.SYNTHETIC_UPLOAD,
        status=IngestionJobStatus.QUEUED,
        source_label=f"{table_name}:{file.filename}",
        requested_by_user_id=int(admin["sub"]),
    )
    created_job = await job_repository.create(job)
    await enqueue_synthetic_upload(table_name, created_job.id, contents)
    return SyntheticUploadResponse(job_id=created_job.id, status=created_job.status.value)


@router.post(
    "/transfermarkt-sync",
    response_model=SyncTriggerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger a roster-scoped Transfermarkt sync",
    description="Admin-only. Queues the scoped Transfermarkt sync pipeline and "
    "returns a job id to poll. With skip_populated=true, a step whose target "
    "table already has rows is skipped instead of re-running -- useful for "
    "resuming after a failure without re-fetching everything from scratch.",
)
async def trigger_transfermarkt_sync(
    admin: AdminDep,
    job_repository: IngestionJobRepositoryDep,
    request: TransfermarktSyncRequest | None = None,
) -> SyncTriggerResponse:
    request = request or TransfermarktSyncRequest()
    job = IngestionJob(
        id=None,
        job_type=IngestionJobType.TRANSFERMARKT_SYNC,
        source_label="full-scoped-sync" if not request.skip_populated else "resume-scoped-sync",
        status=IngestionJobStatus.QUEUED,
        requested_by_user_id=int(admin["sub"]),
    )
    created_job = await job_repository.create(job)
    await enqueue_transfermarkt_sync(created_job.id, request.skip_populated)
    return SyncTriggerResponse(job_id=created_job.id, status=created_job.status.value)


@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    summary="Get an ingestion job's status",
    responses={status.HTTP_404_NOT_FOUND: {"description": "Job not found"}},
)
async def get_job_status(
    job_id: int, admin: AdminDep, job_repository: IngestionJobRepositoryDep
) -> JobStatusResponse:
    job = await job_repository.get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ingestion job not found")
    return JobStatusResponse.from_domain(job)
