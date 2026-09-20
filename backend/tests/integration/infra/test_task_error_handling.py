"""Integration test against a real Postgres instance (no mocking): proves a
failure originating from a real DB statement (a unique-constraint
violation) still leaves the ingestion_job row marked `failed` with the
real error message -- not stuck at `running` with a masking
"transaction aborted" error, which is what happened before `_fail_job`
rolled the session back first.
"""

import asyncio
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy import text

from src.domain.ingestion.model.ingestion_job import (
    IngestionJob,
    IngestionJobStatus,
    IngestionJobType,
)
from src.infra.postgres.config import SessionFactory
from src.infra.postgres.repositories.ingestion_job_repository import (
    _SqlAlchemyIngestionJobRepository,
)
from src.infra.task_queue.tasks import _fail_job

_USER_ID = 990401


@pytest.fixture
async def db_session() -> AsyncGenerator:
    async with SessionFactory() as session:
        await session.execute(
            text(
                'INSERT INTO "user" (id, email, password_hash, is_admin, created_at) '
                "VALUES (:id, :email, 'hash', false, now())"
            ),
            {"id": _USER_ID, "email": f"task-error-test-{_USER_ID}@example.test"},
        )
        await session.commit()
        yield session
    async with SessionFactory() as cleanup_session:
        await cleanup_session.execute(
            text("DELETE FROM ingestion_job WHERE requested_by_user_id = :id"), {"id": _USER_ID}
        )
        await cleanup_session.execute(text('DELETE FROM "user" WHERE id = :id'), {"id": _USER_ID})
        await cleanup_session.commit()


async def test_fail_job_recovers_and_persists_real_error_after_aborted_transaction(
    db_session,
) -> None:
    job_repository = _SqlAlchemyIngestionJobRepository(db_session)
    created = await job_repository.create(
        IngestionJob(
            id=None,
            job_type=IngestionJobType.SYNTHETIC_UPLOAD,
            status=IngestionJobStatus.QUEUED,
            source_label="test",
            requested_by_user_id=_USER_ID,
        )
    )
    running = await job_repository.update(created.mark_running())

    # Provoke a real DB-level failure (unknown column) to abort the
    # session's transaction, exactly like a real constraint violation would.
    with pytest.raises(Exception):  # noqa: B017, PT011 -- any DBAPI error is fine here
        await db_session.execute(text("SELECT this_column_does_not_exist FROM ingestion_job"))

    await _fail_job(db_session, job_repository, running.id, ValueError("real underlying error"))

    reloaded = await job_repository.get(running.id)
    assert reloaded is not None
    assert reloaded.status == IngestionJobStatus.FAILED
    assert reloaded.error_message == "real underlying error"


async def test_fail_job_records_a_readable_message_for_a_cancelled_job(db_session) -> None:
    # arq cancels a job that exceeds JOB_TIMEOUT_SECONDS via
    # asyncio.wait_for -- asyncio.CancelledError is a BaseException, not an
    # Exception, since Python 3.8. Found live: a real sync run exceeded the
    # 30-minute timeout and stayed stuck at `running` forever because the
    # task's `except Exception` never saw the cancellation. str(exc) on a
    # bare CancelledError is also "" -- _fail_job must fall back to the
    # class name so the recorded error isn't blank.
    job_repository = _SqlAlchemyIngestionJobRepository(db_session)
    created = await job_repository.create(
        IngestionJob(
            id=None,
            job_type=IngestionJobType.TRANSFERMARKT_SYNC,
            status=IngestionJobStatus.QUEUED,
            source_label="test",
            requested_by_user_id=_USER_ID,
        )
    )
    running = await job_repository.update(created.mark_running())

    await _fail_job(db_session, job_repository, running.id, asyncio.CancelledError())

    reloaded = await job_repository.get(running.id)
    assert reloaded is not None
    assert reloaded.status == IngestionJobStatus.FAILED
    assert reloaded.error_message == "CancelledError"
