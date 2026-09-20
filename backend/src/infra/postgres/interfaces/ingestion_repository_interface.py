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
    ) -> UpsertResult:
        """Every dict in `rows` must carry the same set of keys. On
        conflict, only the columns actually present in that key set are
        updated -- a column every row intentionally omits (e.g. an
        IDENTITY-assigned primary key, or one this batch doesn't populate)
        is left untouched by the conflicting row's existing value, not
        overwritten by whatever the omitted column's implicit default
        would have been.
        """
        ...

    async def has_rows(self, schema_cls: type[Base]) -> bool:
        """Whether `schema_cls`'s table currently has any rows -- backs the
        Transfermarkt sync's resume mode: a step whose target table is
        already populated can be skipped instead of re-fetching and
        re-upserting a source CSV that can be millions of rows.
        """
        ...

    async def fetch_columns(
        self, schema_cls: type[Base], columns: Sequence[str]
    ) -> list[dict[str, Any]]:
        """Reads back `columns` from every row of `schema_cls`'s table --
        lets a skipped step's downstream consumers (roster scoping, club/
        player scoping) rebuild what they need from already-persisted data
        instead of the source CSV that produced it.
        """
        ...

    async def has_non_null_column(self, schema_cls: type[Base], column: str) -> bool:
        """Whether any row of `schema_cls`'s table has `column` set --
        backs the resume-mode skip signal for a step that only ever
        UPDATEs pre-existing rows (never inserts), where `has_rows` alone
        would always be true regardless of whether that step has run.
        """
        ...

    async def update_matched(
        self,
        schema_cls: type[Base],
        key_column: str,
        rows: list[dict[str, Any]],
    ) -> UpsertResult:
        """UPDATEs existing rows of `schema_cls`'s table, matched by each
        row dict's `key_column` value -- unlike `upsert_many`, a row whose
        key doesn't match an existing one is silently skipped, never
        inserted. Every dict must carry the same set of keys (the columns
        being updated) plus `key_column`.
        """
        ...
