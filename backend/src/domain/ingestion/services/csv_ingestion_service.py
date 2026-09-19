"""Orchestrates parsing + chunked upsert for one `TableIngestionSpec`. Pure
orchestration: DB access happens only through the injected
`IngestionRepositoryInterface`, so this is unit-testable with a fake
repository (no real DB needed).
"""

from collections.abc import Iterable
from typing import Any

from src.domain.ingestion.exceptions.ingestion_exceptions import IngestionValidationError
from src.domain.ingestion.services.table_ingestion_spec import TableIngestionSpec
from src.infra.postgres.interfaces.ingestion_repository_interface import (
    IngestionRepositoryInterface,
)

_DEFAULT_CHUNK_SIZE = 500


class CsvIngestionService:
    async def ingest_rows(
        self,
        spec: TableIngestionSpec,
        rows: Iterable[dict[str, str]],
        repository: IngestionRepositoryInterface,
        chunk_size: int = _DEFAULT_CHUNK_SIZE,
    ) -> int:
        total = 0
        batch: list[dict[str, Any]] = []
        for row_index, raw_row in enumerate(rows):
            batch.append(self._parse_row(spec, row_index, raw_row))
            if len(batch) >= chunk_size:
                await repository.upsert_many(spec.target_schema, batch, spec.conflict_columns)
                total += len(batch)
                batch = []
        if batch:
            await repository.upsert_many(spec.target_schema, batch, spec.conflict_columns)
            total += len(batch)
        return total

    def _parse_row(
        self, spec: TableIngestionSpec, row_index: int, raw_row: dict[str, str]
    ) -> dict[str, Any]:
        table_name = spec.target_schema.__tablename__
        parsed: dict[str, Any] = {}
        for column, parser in spec.column_spec.items():
            if column not in raw_row:
                raise IngestionValidationError(
                    f"row {row_index}: missing column '{column}' for table '{table_name}'"
                )
            try:
                parsed[column] = parser(raw_row[column])
            except (ValueError, TypeError) as exc:
                raise IngestionValidationError(
                    f"row {row_index}: invalid value for column '{column}' "
                    f"for table '{table_name}': {exc}"
                ) from exc
        if spec.row_transform is not None:
            parsed = spec.row_transform(parsed)
        return parsed
