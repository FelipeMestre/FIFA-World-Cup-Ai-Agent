"""Declarative mapper describing how to ingest one CSV-shaped source into one
upsert target table. Adapts `seed_from_csv.py`'s `TABLE_SPECS`/`ColumnSpec`
one-shot-insert pattern for repeatable, idempotent upsert ingestion.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from src.infra.postgres.schemas.base import Base

ColumnSpec = dict[str, Callable[[str], Any]]


@dataclass(frozen=True, slots=True)
class TableIngestionSpec:
    # CSV filename (or logical table key) the source rows come from.
    source_name: str
    target_schema: type[Base]
    column_spec: ColumnSpec
    # Natural-key columns used for `ON CONFLICT DO UPDATE`.
    conflict_columns: tuple[str, ...]
    # Optional post-parse hook, e.g. computing a derived column that has no
    # 1:1 source CSV column.
    row_transform: Callable[[dict[str, Any]], dict[str, Any]] | None = None
