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
from src.domain.ingestion.model.transfermarkt_sync_stage import TransfermarktSyncStage


class IngestionJobType(StrEnum):
    SYNTHETIC_UPLOAD = "synthetic_upload"
    TRANSFERMARKT_SYNC = "transfermarkt_sync"
    IDENTITY_LINK_REMATCH = "identity_link_rematch"


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
    current_stage: str | None = None
    stage_checkpoints: list[dict[str, str]] = field(default_factory=list)
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

    def record_stage_checkpoint(self, stage: TransfermarktSyncStage) -> IngestionJob:
        """Records that `stage` just completed, for a job still `running`.
        Append-only: `stage_checkpoints` is the full history a job-status
        response can render as a progress timeline, while `current_stage`
        alone answers "where is it right now".
        """
        if self.status != IngestionJobStatus.RUNNING:
            raise InvalidJobTransitionError(
                f"cannot record a stage checkpoint for job {self.id} from status "
                f"'{self.status}' (expected '{IngestionJobStatus.RUNNING}')"
            )
        checkpoint = {"stage": stage.value, "completed_at": datetime.now(UTC).isoformat()}
        return replace(
            self,
            current_stage=stage.value,
            stage_checkpoints=[*self.stage_checkpoints, checkpoint],
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
