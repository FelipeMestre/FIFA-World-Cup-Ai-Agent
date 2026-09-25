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
    BulkFileResult,
    BulkSyntheticUploadResponse,
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
from src.domain.ingestion.services.bulk_synthetic_upload_specs import resolve_table_name
from src.infra.postgres.interfaces.ingestion_job_repository_interface import (
    IngestionJobRepositoryInterface,
)
from src.infra.postgres.repositories.ingestion_job_repository import get_ingestion_job_repository
from src.infra.task_queue.pool import (
    enqueue_bulk_synthetic_upload,
    enqueue_synthetic_upload,
    enqueue_transfermarkt_sync,
)

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
    "/bulk-synthetic-upload",
    response_model=BulkSyntheticUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload multiple synthetic CSV files for ingestion as one ordered job",
    description="Admin-only. Infers each file's target table from its filename "
    "against a static map (never a strip-'.csv' heuristic), rejects unrecognized "
    "or invalid files individually without aborting files that did resolve, and "
    "ingests every accepted file as ONE Arq job in a fixed FK-safe order -- "
    "never the order the files were uploaded in.",
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "No uploaded file resolved to a known table"}
    },
)
async def upload_bulk_synthetic_csvs(
    admin: AdminDep,
    job_repository: IngestionJobRepositoryDep,
    files: Annotated[list[UploadFile], File()],
) -> BulkSyntheticUploadResponse:
    results: list[BulkFileResult] = []
    accepted_files: list[tuple[str, bytes]] = []

    for upload in files:
        filename = upload.filename or "<unnamed file>"

        if upload.content_type not in _ALLOWED_CONTENT_TYPES:
            results.append(
                BulkFileResult(
                    filename=filename,
                    table_name=None,
                    accepted=False,
                    reason=f"unsupported content type '{upload.content_type}', expected a CSV",
                )
            )
            continue

        contents = await upload.read(_MAX_UPLOAD_BYTES + 1)
        if len(contents) > _MAX_UPLOAD_BYTES:
            results.append(
                BulkFileResult(
                    filename=filename,
                    table_name=None,
                    accepted=False,
                    reason=f"file exceeds the {_MAX_UPLOAD_BYTES // (1024 * 1024)}MB upload limit",
                )
            )
            continue

        table_name = resolve_table_name(filename)
        if table_name is None:
            results.append(
                BulkFileResult(
                    filename=filename,
                    table_name=None,
                    accepted=False,
                    reason=(
                        f"unrecognized filename '{filename}': does not match any known "
                        "synthetic dataset table"
                    ),
                )
            )
            continue

        results.append(BulkFileResult(filename=filename, table_name=table_name, accepted=True))
        accepted_files.append((filename, contents))

    if not accepted_files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "no uploaded file resolved to a known synthetic dataset table",
                "files": [result.model_dump() for result in results],
            },
        )

    job = IngestionJob(
        id=None,
        job_type=IngestionJobType.BULK_SYNTHETIC_UPLOAD,
        status=IngestionJobStatus.QUEUED,
        source_label=",".join(filename for filename, _ in accepted_files),
        requested_by_user_id=int(admin["sub"]),
    )
    created_job = await job_repository.create(job)
    await enqueue_bulk_synthetic_upload(created_job.id, accepted_files)
    return BulkSyntheticUploadResponse(
        job_id=created_job.id, status=created_job.status.value, files=results
    )


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
