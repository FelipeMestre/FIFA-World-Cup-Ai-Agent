"""Durable admin-facing ingestion job status.

Arq's own Redis result store is not used as the source of truth here: its
default `keep_result` TTL is short-lived and it only stores the raw task
return value, not admin-facing fields like per-table row counts or a human
`source_label`. This table is queryable, durable history for "who triggered
this, and what happened" -- Arq remains the execution/queueing mechanism.
"""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.infra.postgres.schemas.base import Base


class IngestionJobType(StrEnum):
    SYNTHETIC_UPLOAD = "synthetic_upload"
    TRANSFERMARKT_SYNC = "transfermarkt_sync"


class IngestionJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class IngestionJobSchema(Base):
    __tablename__ = "ingestion_job"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_type: Mapped[IngestionJobType] = mapped_column(
        SAEnum(IngestionJobType, name="ingestion_job_type"), nullable=False
    )
    status: Mapped[IngestionJobStatus] = mapped_column(
        SAEnum(IngestionJobStatus, name="ingestion_job_status"), nullable=False, index=True
    )
    source_label: Mapped[str] = mapped_column(nullable=False)
    row_counts: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error_message: Mapped[str | None] = mapped_column(nullable=True)
    requested_by_user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
