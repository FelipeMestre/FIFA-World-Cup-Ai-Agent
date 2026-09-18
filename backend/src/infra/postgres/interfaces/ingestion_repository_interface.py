"""Generic bulk-upsert repository contract for ingested tables.

Deliberate deviation from the codebase's usual one-repository-per-entity
convention: the upsert shape (parse -> batch -> `ON CONFLICT DO UPDATE`) is
identical across every ingested table (~19 tables across synthetic and
Transfermarkt sources) and differs only by `schema_cls`/`conflict_columns`.
One generic repository avoids ~19 near-identical boilerplate files. The
existing per-entity pattern (e.g. `team_repository.py`) was designed for
read-side domain mapping, which bulk upsert doesn't need.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from src.infra.postgres.schemas.base import Base


@dataclass(frozen=True)
class UpsertResult:
    table_name: str
    row_count: int


class IngestionRepositoryInterface(Protocol):
    async def upsert_many(
        self,
        schema_cls: type[Base],
        rows: list[dict[str, Any]],
        conflict_columns: Sequence[str],
    ) -> UpsertResult: ...
