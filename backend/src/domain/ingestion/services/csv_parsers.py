"""Shared CSV column-value parser helpers, extracted from
`backend/scripts/seed_from_csv.py`'s private parser functions so both
synthetic and Transfermarkt `TableIngestionSpec` instances can reuse them
without duplicating the logic.
"""

from datetime import date, time


def parse_int(value: str) -> int:
    return int(value)


def parse_optional_int(value: str) -> int | None:
    return int(value) if value else None


def parse_float(value: str) -> float:
    return float(value)


def parse_optional_float(value: str) -> float | None:
    return float(value) if value else None


def parse_str(value: str) -> str:
    return value


def parse_optional_str(value: str) -> str | None:
    return value if value else None


def parse_bool(value: str) -> bool:
    return value.strip().lower() in {"true", "1"}


def parse_date(value: str) -> date:
    # Some real Transfermarkt columns (e.g. players.csv date_of_birth) carry
    # a full timestamp ("1978-06-09 00:00:00") rather than a bare date;
    # date.fromisoformat only accepts the latter, so take the date portion.
    return date.fromisoformat(value.split(" ")[0])


def parse_optional_date(value: str) -> date | None:
    return date.fromisoformat(value.split(" ")[0]) if value else None


def parse_time(value: str) -> time:
    return time.fromisoformat(value)
