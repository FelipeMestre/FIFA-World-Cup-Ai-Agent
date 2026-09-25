"""Batch variant of `SyntheticIngestionService`: ingests multiple (filename,
bytes) CSV pairs as ONE `IngestionJob`, resolving each filename's target
table via `bulk_synthetic_upload_specs`, sorting accepted files into the
fixed FK-safe order regardless of upload order, and accumulating per-table
`row_counts` on the job -- the same `dict[str, int]` shape
`TransfermarktSyncService` already accumulates across many tables on one job.

`resolve_and_order_files` is a pure, dependency-free function so the router
can call it synchronously (before any job exists) to build its immediate
per-file accept/reject response, while `BulkSyntheticIngestionService.
ingest_batch` does the actual (async, DB-backed) ingestion inside the Arq
task -- both paths share the exact same resolution/ordering rule instead of
duplicating it.
"""

import csv
import io
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from src.domain.ingestion.exceptions.ingestion_exceptions import IngestionValidationError
from src.domain.ingestion.model.ingestion_job import IngestionJob
from src.domain.ingestion.services.bulk_synthetic_upload_specs import (
    ingestion_order_index,
    resolve_table_name,
)
from src.domain.ingestion.services.csv_ingestion_service import CsvIngestionService
from src.domain.ingestion.services.synthetic_table_specs import SYNTHETIC_TABLE_SPECS
from src.domain.ingestion.services.table_ingestion_spec import TableIngestionSpec
from src.infra.postgres.interfaces.ingestion_job_repository_interface import (
    IngestionJobRepositoryInterface,
)
from src.infra.postgres.interfaces.ingestion_repository_interface import (
    IngestionRepositoryInterface,
)


@dataclass(frozen=True, slots=True)
class ResolvedFile:
    filename: str
    table_name: str
    csv_bytes: bytes


@dataclass(frozen=True, slots=True)
class RejectedFile:
    filename: str
    reason: str


@dataclass(frozen=True, slots=True)
class BatchResolution:
    accepted: list[ResolvedFile] = field(default_factory=list)
    rejected: list[RejectedFile] = field(default_factory=list)


def resolve_and_order_files(files: Sequence[tuple[str, bytes]]) -> BatchResolution:
    """Resolves each uploaded filename to its target table, rejecting (never
    guess-routing) any filename absent from the map, then sorts every
    accepted file into the fixed FK-safe ingestion order -- regardless of the
    order the caller passed them in.
    """
    accepted: list[ResolvedFile] = []
    rejected: list[RejectedFile] = []
    for filename, csv_bytes in files:
        table_name = resolve_table_name(filename)
        if table_name is None:
            rejected.append(
                RejectedFile(
                    filename=filename,
                    reason=(
                        f"unrecognized filename '{filename}': does not match any known "
                        "synthetic dataset table"
                    ),
                )
            )
            continue
        accepted.append(
            ResolvedFile(filename=filename, table_name=table_name, csv_bytes=csv_bytes)
        )
    accepted.sort(key=lambda resolved: ingestion_order_index(resolved.table_name))
    return BatchResolution(accepted=accepted, rejected=rejected)


def _parse_csv_rows(csv_bytes: bytes) -> list[dict[str, str]]:
    text = io.StringIO(csv_bytes.decode("utf-8"))
    return list(csv.DictReader(text))


class BulkSyntheticIngestionService:
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

    async def ingest_batch(
        self, resolved_files: Iterable[ResolvedFile], job: IngestionJob
    ) -> IngestionJob:
        running_job = job.mark_running()
        running_job = await self._ingestion_job_repository.update(running_job)

        row_counts: dict[str, int] = {}
        try:
            for resolved in resolved_files:
                spec = self._specs_by_name[resolved.table_name]
                rows: list[dict[str, Any]] = _parse_csv_rows(resolved.csv_bytes)
                count = await self._csv_ingestion_service.ingest_rows(
                    spec, rows, self._ingestion_repository
                )
                row_counts[resolved.table_name] = row_counts.get(resolved.table_name, 0) + count
        except IngestionValidationError as exc:
            failed_job = running_job.mark_failed(str(exc))
            return await self._ingestion_job_repository.update(failed_job)

        succeeded_job = running_job.mark_succeeded(row_counts)
        return await self._ingestion_job_repository.update(succeeded_job)
