from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.ingestion.model.ingestion_job import (
    IngestionJob,
    IngestionJobStatus,
    IngestionJobType,
)
from src.infra.postgres.config import get_db
from src.infra.postgres.interfaces.ingestion_job_repository_interface import (
    IngestionJobRepositoryInterface,
)
from src.infra.postgres.schemas.ingestion_job_schema import IngestionJobSchema
from src.infra.postgres.schemas.ingestion_job_schema import IngestionJobStatus as SchemaJobStatus
from src.infra.postgres.schemas.ingestion_job_schema import IngestionJobType as SchemaJobType


def _to_domain(row: IngestionJobSchema) -> IngestionJob:
    return IngestionJob(
        id=row.id,
        job_type=IngestionJobType(row.job_type.value),
        status=IngestionJobStatus(row.status.value),
        source_label=row.source_label,
        requested_by_user_id=row.requested_by_user_id,
        row_counts=row.row_counts,
        error_message=row.error_message,
        created_at=row.created_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
    )


class _SqlAlchemyIngestionJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, job: IngestionJob) -> IngestionJob:
        row = IngestionJobSchema(
            job_type=SchemaJobType(job.job_type.value),
            status=SchemaJobStatus(job.status.value),
            source_label=job.source_label,
            row_counts=job.row_counts,
            error_message=job.error_message,
            requested_by_user_id=job.requested_by_user_id,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_domain(row)

    async def get(self, job_id: int) -> IngestionJob | None:
        row = await self._session.get(IngestionJobSchema, job_id)
        return _to_domain(row) if row else None

    async def update(self, job: IngestionJob) -> IngestionJob:
        if job.id is None:
            raise ValueError("cannot update an IngestionJob that has no id")
        row = await self._session.get(IngestionJobSchema, job.id)
        if row is None:
            raise ValueError(f"ingestion_job {job.id} not found")
        row.status = SchemaJobStatus(job.status.value)
        row.row_counts = job.row_counts
        row.error_message = job.error_message
        row.started_at = job.started_at
        row.finished_at = job.finished_at
        await self._session.commit()
        await self._session.refresh(row)
        return _to_domain(row)


def get_ingestion_job_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> IngestionJobRepositoryInterface:
    return _SqlAlchemyIngestionJobRepository(session)
