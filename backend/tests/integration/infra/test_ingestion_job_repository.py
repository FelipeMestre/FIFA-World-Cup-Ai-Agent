"""Integration tests against a real Postgres instance (no mocking, per
AGENTS.md's testing anti-pattern table): verifies `IngestionJobRepository`'s
create/get/update round-trip and its `IngestionJob` <-> `IngestionJobSchema`
mapping.
"""

from collections.abc import AsyncGenerator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.ingestion.model.ingestion_job import (
    IngestionJob,
    IngestionJobStatus,
    IngestionJobType,
)
from src.domain.ingestion.model.transfermarkt_sync_stage import TransfermarktSyncStage
from src.infra.postgres.config import SessionFactory, engine
from src.infra.postgres.repositories.ingestion_job_repository import (
    _SqlAlchemyIngestionJobRepository,
)

_USER_ID = 990101


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    async with SessionFactory() as session:
        await session.execute(
            text(
                'INSERT INTO "user" (id, email, name, password_hash, is_admin, created_at) '
                "VALUES (:id, :email, split_part(:email, '@', 1), 'hash', false, now())"
            ),
            {"id": _USER_ID, "email": f"ingestion-job-test-{_USER_ID}@example.test"},
        )
        await session.commit()
        yield session
    async with SessionFactory() as cleanup_session:
        await cleanup_session.execute(
            text("DELETE FROM ingestion_job WHERE requested_by_user_id = :id"), {"id": _USER_ID}
        )
        await cleanup_session.execute(text('DELETE FROM "user" WHERE id = :id'), {"id": _USER_ID})
        await cleanup_session.commit()
    await engine.dispose()


def _queued_job() -> IngestionJob:
    return IngestionJob(
        id=None,
        job_type=IngestionJobType.SYNTHETIC_UPLOAD,
        status=IngestionJobStatus.QUEUED,
        source_label="team.csv",
        requested_by_user_id=_USER_ID,
    )


async def test_create_persists_and_returns_a_domain_job(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyIngestionJobRepository(db_session)

    created = await repository.create(_queued_job())

    assert created.id is not None
    assert created.status == IngestionJobStatus.QUEUED
    assert created.row_counts == {}


async def test_get_returns_none_for_unknown_id(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyIngestionJobRepository(db_session)

    assert await repository.get(-1) is None


async def test_update_persists_status_transition(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyIngestionJobRepository(db_session)
    created = await repository.create(_queued_job())
    running_job = created.mark_running()

    updated = await repository.update(running_job)

    assert updated.status == IngestionJobStatus.RUNNING
    assert updated.started_at is not None
    reloaded = await repository.get(created.id)
    assert reloaded is not None
    assert reloaded.status == IngestionJobStatus.RUNNING


async def test_update_persists_succeeded_row_counts(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyIngestionJobRepository(db_session)
    created = await repository.create(_queued_job())
    succeeded_job = created.mark_running().mark_succeeded({"team": 48})

    updated = await repository.update(succeeded_job)

    assert updated.status == IngestionJobStatus.SUCCEEDED
    assert updated.row_counts == {"team": 48}


async def test_update_persists_stage_checkpoints(db_session: AsyncSession) -> None:
    repository = _SqlAlchemyIngestionJobRepository(db_session)
    created = await repository.create(
        IngestionJob(
            id=None,
            job_type=IngestionJobType.TRANSFERMARKT_SYNC,
            status=IngestionJobStatus.QUEUED,
            source_label="full-scoped-sync",
            requested_by_user_id=_USER_ID,
        )
    )
    running_job = await repository.update(created.mark_running())

    checkpointed = await repository.update(
        running_job.record_stage_checkpoint(TransfermarktSyncStage.NATIONAL_TEAMS)
    )

    assert checkpointed.current_stage == "national_teams"
    assert [c["stage"] for c in checkpointed.stage_checkpoints] == ["national_teams"]
    reloaded = await repository.get(created.id)
    assert reloaded is not None
    assert reloaded.current_stage == "national_teams"
    assert [c["stage"] for c in reloaded.stage_checkpoints] == ["national_teams"]
