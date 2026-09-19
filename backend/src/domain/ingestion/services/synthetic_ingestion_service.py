"""Top-level service the admin synthetic-upload endpoint (PR 5) calls: looks
up the `TableIngestionSpec` for the requested table, delegates parsing +
upsert to `CsvIngestionService`, and drives the `IngestionJob` through its
`running` -> `succeeded`/`failed` transitions, persisting each transition.
"""

from collections.abc import Iterable, Sequence

from src.domain.ingestion.exceptions.ingestion_exceptions import (
    IngestionValidationError,
    UnknownTableError,
)
from src.domain.ingestion.model.ingestion_job import IngestionJob
from src.domain.ingestion.services.csv_ingestion_service import CsvIngestionService
from src.domain.ingestion.services.synthetic_table_specs import SYNTHETIC_TABLE_SPECS
from src.domain.ingestion.services.table_ingestion_spec import TableIngestionSpec
from src.infra.postgres.interfaces.ingestion_job_repository_interface import (
    IngestionJobRepositoryInterface,
)
from src.infra.postgres.interfaces.ingestion_repository_interface import (
    IngestionRepositoryInterface,
)


class SyntheticIngestionService:
    def __init__(
        self,
        csv_ingestion_service: CsvIngestionService,
        ingestion_repository: IngestionRepositoryInterface,
        ingestion_job_repository: IngestionJobRepositoryInterface,
        table_specs: Sequence[TableIngestionSpec] = SYNTHETIC_TABLE_SPECS,
    ) -> None:
        self._csv_ingestion_service = csv_ingestion_service
        self._ingestion_repository = ingestion_repository
        self._ingestion_job_repository = ingestion_job_repository
        self._specs_by_name = {spec.source_name: spec for spec in table_specs}

    async def ingest_upload(
        self, table_name: str, rows: Iterable[dict[str, str]], job: IngestionJob
    ) -> IngestionJob:
        spec = self._specs_by_name.get(table_name)
        if spec is None:
            raise UnknownTableError(f"unknown synthetic ingestion table '{table_name}'")

        running_job = job.mark_running()
        running_job = await self._ingestion_job_repository.update(running_job)

        try:
            row_count = await self._csv_ingestion_service.ingest_rows(
                spec, rows, self._ingestion_repository
            )
        except IngestionValidationError as exc:
            failed_job = running_job.mark_failed(str(exc))
            return await self._ingestion_job_repository.update(failed_job)

        succeeded_job = running_job.mark_succeeded({table_name: row_count})
        return await self._ingestion_job_repository.update(succeeded_job)
