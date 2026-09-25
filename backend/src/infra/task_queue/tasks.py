"""Arq task functions the worker actually runs. Each opens its own
`session_scope()` (no FastAPI `Depends` graph is available here), builds the
concrete repositories/services directly, and drives the corresponding
domain service.

On any failure, `_fail_job` rolls the session back *before* writing the
`failed` status: a failure that originates from a DB statement (e.g. an
upsert constraint violation) leaves the session's transaction aborted, and
any further statement on that same session -- including the mark_failed()
write itself -- fails too until a rollback happens. Without the rollback,
the real error gets replaced by a second, unrelated "transaction aborted"
error, and the job is left stuck at `running` forever with no error
message recorded. Found live: a real sync run hit exactly this, and the
worker log showed only the masking error, not the original one.

Both task functions catch `BaseException`, not `Exception`: arq enforces
`JOB_TIMEOUT_SECONDS` via `asyncio.wait_for`, which cancels the running
task on timeout -- and `asyncio.CancelledError` is a `BaseException`, not
an `Exception`, since Python 3.8. `except Exception` alone silently lets a
timeout-cancelled job skip `_fail_job` entirely, leaving it stuck at
`running` forever with no error message, even though arq itself already
gave up on it. Found live: a Transfermarkt sync exceeded the 30-minute
job timeout and stayed `running` in the DB indefinitely.

The synthetic-upload task receives the CSV as raw bytes in the job payload
rather than a filesystem path: the API and worker run in separate
containers with separate filesystems, so a path written by the API process
is not visible to the worker process.
"""

import csv
import io
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.ingestion.model.ingestion_job import IngestionJobStatus
from src.domain.ingestion.services.csv_ingestion_service import CsvIngestionService
from src.domain.ingestion.services.identity_link_rematch_service import IdentityLinkRematchService
from src.domain.ingestion.services.player_identity_matching_service import (
    PlayerIdentityMatchingService,
)
from src.domain.ingestion.services.roster_scoping_service import RosterScopingService
from src.domain.ingestion.services.season_stat_aggregation_service import (
    SeasonStatAggregationService,
)
from src.domain.ingestion.services.synthetic_ingestion_service import SyntheticIngestionService
from src.domain.ingestion.services.transfermarkt_detail_sync import TransfermarktDetailSync
from src.domain.ingestion.services.transfermarkt_sync_service import TransfermarktSyncService
from src.infra.postgres.interfaces.ingestion_job_repository_interface import (
    IngestionJobRepositoryInterface,
)
from src.infra.postgres.repositories.ingestion_job_repository import (
    _SqlAlchemyIngestionJobRepository,
)
from src.infra.postgres.repositories.ingestion_repository import _SqlAlchemyIngestionRepository
from src.infra.postgres.repositories.national_team_repository import (
    _SqlAlchemyNationalTeamRepository,
)
from src.infra.postgres.repositories.player_identity_link_repository import (
    _SqlAlchemyPlayerIdentityLinkRepository,
)
from src.infra.postgres.repositories.player_repository import _SqlAlchemyPlayerRepository
from src.infra.postgres.repositories.real_player_repository import _SqlAlchemyRealPlayerRepository
from src.infra.task_queue.session_scope import session_scope
from src.infra.transfermarkt.client import get_transfermarkt_client

logger = logging.getLogger(__name__)


def _parse_csv_rows(csv_bytes: bytes) -> list[dict[str, Any]]:
    text = io.StringIO(csv_bytes.decode("utf-8"))
    return list(csv.DictReader(text))


async def _fail_job(
    session: AsyncSession,
    job_repository: IngestionJobRepositoryInterface,
    job_id: int,
    exc: BaseException,
) -> None:
    logger.exception("ingestion_job %s failed", job_id, exc_info=exc)
    await session.rollback()
    current = await job_repository.get(job_id)
    if current is not None and current.status in (
        IngestionJobStatus.QUEUED,
        IngestionJobStatus.RUNNING,
    ):
        # str(asyncio.CancelledError()) is "" -- fall back to the class name
        # so a job cancelled by arq's JOB_TIMEOUT_SECONDS still gets a
        # readable error_message instead of an empty string.
        message = str(exc) or exc.__class__.__name__
        await job_repository.update(current.mark_failed(message))


async def synthetic_upload_task(ctx: dict, job_id: int, table_name: str, csv_bytes: bytes) -> None:
    async with session_scope() as session:
        job_repository = _SqlAlchemyIngestionJobRepository(session)
        job = await job_repository.get(job_id)
        if job is None:
            raise ValueError(f"ingestion_job {job_id} not found")

        service = SyntheticIngestionService(
            csv_ingestion_service=CsvIngestionService(),
            ingestion_repository=_SqlAlchemyIngestionRepository(session),
            ingestion_job_repository=job_repository,
        )
        try:
            await service.ingest_upload(table_name, _parse_csv_rows(csv_bytes), job)
        except BaseException as exc:
            await _fail_job(session, job_repository, job_id, exc)
            raise


async def transfermarkt_sync_task(ctx: dict, job_id: int, skip_populated: bool = False) -> None:
    async with session_scope() as session:
        job_repository = _SqlAlchemyIngestionJobRepository(session)
        job = await job_repository.get(job_id)
        if job is None:
            raise ValueError(f"ingestion_job {job_id} not found")

        ingestion_repository = _SqlAlchemyIngestionRepository(session)
        transfermarkt_client = get_transfermarkt_client()
        service = TransfermarktSyncService(
            transfermarkt_client=transfermarkt_client,
            csv_ingestion_service=CsvIngestionService(),
            ingestion_repository=ingestion_repository,
            ingestion_job_repository=job_repository,
            national_team_repository=_SqlAlchemyNationalTeamRepository(session),
            player_repository=_SqlAlchemyPlayerRepository(session),
            identity_link_repository=_SqlAlchemyPlayerIdentityLinkRepository(session),
            roster_scoping_service=RosterScopingService(),
            matching_service=PlayerIdentityMatchingService(),
            detail_sync=TransfermarktDetailSync(
                transfermarkt_client=transfermarkt_client,
                csv_ingestion_service=CsvIngestionService(),
                ingestion_repository=ingestion_repository,
                season_stat_aggregation_service=SeasonStatAggregationService(),
            ),
        )
        try:
            await service.run_sync(job, skip_populated)
        except BaseException as exc:
            await _fail_job(session, job_repository, job_id, exc)
            raise


async def identity_link_rematch_task(ctx: dict, job_id: int) -> None:
    async with session_scope() as session:
        job_repository = _SqlAlchemyIngestionJobRepository(session)
        job = await job_repository.get(job_id)
        if job is None:
            raise ValueError(f"ingestion_job {job_id} not found")

        service = IdentityLinkRematchService(
            identity_link_repository=_SqlAlchemyPlayerIdentityLinkRepository(session),
            player_repository=_SqlAlchemyPlayerRepository(session),
            real_player_repository=_SqlAlchemyRealPlayerRepository(session),
            ingestion_repository=_SqlAlchemyIngestionRepository(session),
            ingestion_job_repository=job_repository,
            matching_service=PlayerIdentityMatchingService(),
        )
        try:
            await service.rematch(job)
        except BaseException as exc:
            await _fail_job(session, job_repository, job_id, exc)
            raise
