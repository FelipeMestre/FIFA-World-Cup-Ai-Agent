"""Pure unit tests for `IngestionJob`'s state-transition methods -- no DB, no
HTTP. Confirms valid transitions succeed and invalid ones raise
`InvalidJobTransitionError` rather than silently proceeding, per AGENTS.md's
fail-fast philosophy.
"""

import pytest

from src.domain.ingestion.exceptions.ingestion_exceptions import InvalidJobTransitionError
from src.domain.ingestion.model.ingestion_job import (
    IngestionJob,
    IngestionJobStatus,
    IngestionJobType,
)
from src.domain.ingestion.model.transfermarkt_sync_stage import TransfermarktSyncStage


def _queued_job() -> IngestionJob:
    return IngestionJob(
        id=1,
        job_type=IngestionJobType.SYNTHETIC_UPLOAD,
        status=IngestionJobStatus.QUEUED,
        source_label="team.csv",
        requested_by_user_id=42,
    )


def test_mark_running_from_queued_succeeds() -> None:
    job = _queued_job()

    running_job = job.mark_running()

    assert running_job.status == IngestionJobStatus.RUNNING
    assert running_job.started_at is not None
    assert job.status == IngestionJobStatus.QUEUED, "original job must stay immutable"


def test_mark_running_from_succeeded_raises() -> None:
    succeeded_job = _queued_job().mark_running().mark_succeeded({"team": 48})

    with pytest.raises(InvalidJobTransitionError):
        succeeded_job.mark_running()


def test_mark_succeeded_from_running_succeeds() -> None:
    running_job = _queued_job().mark_running()

    succeeded_job = running_job.mark_succeeded({"team": 48})

    assert succeeded_job.status == IngestionJobStatus.SUCCEEDED
    assert succeeded_job.row_counts == {"team": 48}
    assert succeeded_job.finished_at is not None


def test_mark_succeeded_from_queued_raises() -> None:
    queued_job = _queued_job()

    with pytest.raises(InvalidJobTransitionError):
        queued_job.mark_succeeded({"team": 48})


def test_mark_failed_from_running_succeeds() -> None:
    running_job = _queued_job().mark_running()

    failed_job = running_job.mark_failed("boom")

    assert failed_job.status == IngestionJobStatus.FAILED
    assert failed_job.error_message == "boom"
    assert failed_job.finished_at is not None


def test_mark_failed_from_queued_succeeds() -> None:
    """A job can fail before the worker ever marks it running (e.g. an
    unknown table name discovered before any row is processed).
    """
    queued_job = _queued_job()

    failed_job = queued_job.mark_failed("unknown table")

    assert failed_job.status == IngestionJobStatus.FAILED


def test_mark_failed_from_succeeded_raises() -> None:
    succeeded_job = _queued_job().mark_running().mark_succeeded({"team": 48})

    with pytest.raises(InvalidJobTransitionError):
        succeeded_job.mark_failed("too late")


def test_record_stage_checkpoint_from_running_succeeds() -> None:
    running_job = _queued_job().mark_running()

    checkpointed = running_job.record_stage_checkpoint(TransfermarktSyncStage.CLUBS)

    assert checkpointed.current_stage == "clubs"
    assert len(checkpointed.stage_checkpoints) == 1
    assert checkpointed.stage_checkpoints[0]["stage"] == "clubs"
    assert checkpointed.stage_checkpoints[0]["completed_at"]
    assert running_job.stage_checkpoints == [], "original job must stay immutable"


def test_record_stage_checkpoint_accumulates_history_in_order() -> None:
    job = _queued_job().mark_running()

    job = job.record_stage_checkpoint(TransfermarktSyncStage.NATIONAL_TEAMS)
    job = job.record_stage_checkpoint(TransfermarktSyncStage.CLUBS)

    assert [checkpoint["stage"] for checkpoint in job.stage_checkpoints] == [
        "national_teams",
        "clubs",
    ]
    assert job.current_stage == "clubs"


def test_record_stage_checkpoint_from_queued_raises() -> None:
    queued_job = _queued_job()

    with pytest.raises(InvalidJobTransitionError):
        queued_job.record_stage_checkpoint(TransfermarktSyncStage.CLUBS)


def test_record_stage_checkpoint_from_succeeded_raises() -> None:
    succeeded_job = _queued_job().mark_running().mark_succeeded({"team": 48})

    with pytest.raises(InvalidJobTransitionError):
        succeeded_job.record_stage_checkpoint(TransfermarktSyncStage.CLUBS)
