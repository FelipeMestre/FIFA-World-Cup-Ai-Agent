"""Reusable request-boundary guard: fail fast on an unknown upload target
before a job is created or a file is written to disk.
"""

from fastapi import HTTPException, status

from src.domain.ingestion.services.synthetic_table_specs import SYNTHETIC_TABLE_SPECS

_KNOWN_TABLE_NAMES = frozenset(spec.source_name for spec in SYNTHETIC_TABLE_SPECS)


def validate_known_table(table_name: str) -> None:
    if table_name not in _KNOWN_TABLE_NAMES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unknown synthetic ingestion table '{table_name}'",
        )
