"""Arq task functions the worker actually runs. Each opens its own
`session_scope()` (no FastAPI `Depends` graph is available here), builds the
concrete repositories/services directly, and drives the corresponding
domain service. Domain exceptions are caught only to record the job's
`failed` status before re-raising, so Arq's own retry/logging still applies.
"""

import csv
from pathlib import Path
from typing import Any

from src.domain.ingestion.exceptions.ingestion_exceptions import IngestionError
from src.domain.ingestion.services.csv_ingestion_service import CsvIngestionService
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
from src.infra.postgres.repositories.ingestion_job_repository import (
    _SqlAlchemyIngestionJobRepository,
)
from src.infra.postgres.repositories.ingestion_repository import _SqlAlchemyIngestionRepository
from src.infra.postgres.repositories.player_identity_link_repository import (
    _SqlAlchemyPlayerIdentityLinkRepository,
)
from src.infra.postgres.repositories.player_repository import _SqlAlchemyPlayerRepository
from src.infra.postgres.repositories.team_repository import _SqlAlchemyTeamRepository
from src.infra.task_queue.session_scope import session_scope
from src.infra.transfermarkt.client import get_transfermarkt_client


def _read_csv_rows(csv_path: str) -> list[dict[str, Any]]:
    with Path(csv_path).open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


async def synthetic_upload_task(ctx: dict, job_id: int, table_name: str, csv_path: str) -> None:
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
            await service.ingest_upload(table_name, _read_csv_rows(csv_path), job)
        finally:
            Path(csv_path).unlink(missing_ok=True)


async def transfermarkt_sync_task(ctx: dict, job_id: int) -> None:
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
            team_repository=_SqlAlchemyTeamRepository(session),
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
            await service.run_sync(job)
        except IngestionError:
            # run_sync already persisted job.mark_failed(...) before
            # re-raising; this branch exists only to document that domain
            # failures are not swallowed here, Arq still sees/logs them.
            raise
