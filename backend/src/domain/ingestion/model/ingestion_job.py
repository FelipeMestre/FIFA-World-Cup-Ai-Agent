"""Domain object for a durable, admin-facing ingestion job (synthetic CSV
upload or Transfermarkt sync). State transitions are enforced here rather
than left to callers, so an invalid transition (e.g. marking an already
`succeeded` job `running` again) fails loudly instead of silently
overwriting job state.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum

from src.domain.ingestion.exceptions.ingestion_exceptions import InvalidJobTransitionError


class IngestionJobType(StrEnum):
    SYNTHETIC_UPLOAD = "synthetic_upload"
    TRANSFERMARKT_SYNC = "transfermarkt_sync"


class IngestionJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class IngestionJob:
    id: int | None
    job_type: IngestionJobType
    status: IngestionJobStatus
    source_label: str
    requested_by_user_id: int
    row_counts: dict[str, int] = field(default_factory=dict)
    error_message: str | None = None
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None

    def mark_running(self) -> IngestionJob:
        if self.status != IngestionJobStatus.QUEUED:
            raise InvalidJobTransitionError(
                f"cannot mark job {self.id} running from status '{self.status}' "
                f"(expected '{IngestionJobStatus.QUEUED}')"
            )
        return replace(self, status=IngestionJobStatus.RUNNING, started_at=datetime.now(UTC))

    def mark_succeeded(self, row_counts: dict[str, int]) -> IngestionJob:
        if self.status != IngestionJobStatus.RUNNING:
            raise InvalidJobTransitionError(
                f"cannot mark job {self.id} succeeded from status '{self.status}' "
                f"(expected '{IngestionJobStatus.RUNNING}')"
            )
        return replace(
            self,
            status=IngestionJobStatus.SUCCEEDED,
            row_counts=row_counts,
            finished_at=datetime.now(UTC),
        )

    def mark_failed(self, error: str) -> IngestionJob:
        if self.status not in (IngestionJobStatus.QUEUED, IngestionJobStatus.RUNNING):
            raise InvalidJobTransitionError(
                f"cannot mark job {self.id} failed from status '{self.status}' "
                f"(expected '{IngestionJobStatus.QUEUED}' or '{IngestionJobStatus.RUNNING}')"
            )
        return replace(
            self,
            status=IngestionJobStatus.FAILED,
            error_message=error,
            finished_at=datetime.now(UTC),
        )
